import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from pwdlib import PasswordHash
from app.api.routes import router
from app.infrastructure.database import Base, SessionLocal, engine
from app.infrastructure.models import MachineRow, SensorRow, ThresholdRow, UserRow
from app.infrastructure.mqtt_client import MqttIngestor
from app.settings import settings

logging.basicConfig(level=logging.INFO)
passwords = PasswordHash.recommended()


def initialize_data():
    Base.metadata.create_all(bind=engine)
    # create_all creates new tables but does not add columns to an existing volume.
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE machines ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_measurements_machine_recorded_at ON measurements (machine_id, recorded_at)"))
    db = SessionLocal()
    try:
        if db.get(MachineRow, "demo-machine") is None:
            db.add(MachineRow(id="demo-machine", name="Machine de démonstration", description="Banc ESP32 PrediMaint"))
            db.flush()
        seed_users = [
            ("tech@predimaint.local", settings.demo_tech_password, "technician"),
            ("manager@predimaint.local", settings.demo_manager_password, "manager"),
            ("director@predimaint.local", settings.demo_director_password, "director"),
        ]
        for email, password, role in seed_users:
            if not db.scalar(select(UserRow).where(UserRow.email == email)):
                db.add(UserRow(email=email, password_hash=passwords.hash(password), role=role))
        defaults = [("temperature", 60, 75), ("humidity", 85, 95), ("vibration_rate", 10, 30), ("current_rms", 3, 5)]
        for metric, warning, critical in defaults:
            if not db.scalar(select(ThresholdRow).where(ThresholdRow.machine_id == "demo-machine", ThresholdRow.metric == metric)):
                db.add(ThresholdRow(machine_id="demo-machine", metric=metric, warning=warning, critical=critical))
        default_sensors = [
            ("temperature", "DHT22", 27, "°C"),
            ("humidity", "DHT22", 27, "%"),
            ("vibration_rate", "HW-072 numérique", 16, "événements/s"),
            ("current_rms", "ACS712 (courant simulé par défaut)", 34, "A"),
        ]
        for metric, sensor_type, gpio, unit in default_sensors:
            if not db.scalar(select(SensorRow).where(SensorRow.machine_id == "demo-machine", SensorRow.metric == metric)):
                db.add(SensorRow(machine_id="demo-machine", metric=metric, sensor_type=sensor_type, gpio=gpio, unit=unit))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_data()
    ingestor = None
    if settings.mqtt_enabled:
        ingestor = MqttIngestor()
        ingestor.start()
        app.state.mqtt_ingestor = ingestor
    yield
    if ingestor is not None:
        ingestor.stop()


app = FastAPI(title="PrediMaint API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(static_dir / "index.html")
