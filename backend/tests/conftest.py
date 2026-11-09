import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-for-release-one-only-1234567890"
os.environ["MQTT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.auth import get_db, hash_password
from app.infrastructure.database import Base
from app.infrastructure.models import MachineRow, ThresholdRow, UserRow
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

@pytest.fixture()
def client():
    Base.metadata.create_all(engine)
    db = TestingSession()
    db.add(MachineRow(id="test-machine", name="Test"))
    db.add_all([UserRow(email=f"{role}@test.local", password_hash=hash_password("secret-pass"), role=role) for role in ("technician", "manager", "director")])
    db.add(ThresholdRow(machine_id="test-machine", metric="temperature", warning=50, critical=70))
    db.commit(); db.close()
    def override_db():
        session = TestingSession()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)

def auth(client, role):
    result = client.post("/api/auth/login", json={"email": f"{role}@test.local", "password": "secret-pass"})
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['access_token']}"}
