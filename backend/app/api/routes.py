from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.auth import authenticate, current_user, get_db, issue_token, require_roles
from app.application.services import MeasurementInput
from app.infrastructure.models import (
    AlertRow,
    InterventionRow,
    MachineRow,
    MeasurementRow,
    SensorRow,
    ThresholdRow,
    UserRow,
)
from app.infrastructure.repository import SqlMeasurementRepository

router = APIRouter(prefix="/api")
MANAGERS = ("manager",)
MAINTENANCE = ("technician", "manager")
METRICS = {"temperature", "humidity", "vibration_rate", "current_rms"}


class LoginInput(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class ThresholdInput(BaseModel):
    warning: float = Field(ge=0)
    critical: float = Field(gt=0)
    enabled: bool = True


class InterventionInput(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    duration_minutes: int = Field(default=0, ge=0, le=100000)
    alert_id: int | None = None


class MachineCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)


class MachineUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    active: bool = True


class SensorCreate(BaseModel):
    metric: Literal["temperature", "humidity", "vibration_rate", "current_rms"]
    sensor_type: str = Field(min_length=2, max_length=80)
    gpio: int | None = Field(default=None, ge=0, le=39)
    unit: str = Field(min_length=1, max_length=20)


class SensorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sensor_type: str | None = Field(default=None, min_length=2, max_length=80)
    gpio: int | None = Field(default=None, ge=0, le=39)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    enabled: bool | None = None


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/auth/login")
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = authenticate(db, data.email, data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants incorrects")
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "role": user.role,
        "email": user.email,
    }


@router.get("/auth/me")
def me(user: UserRow = Depends(current_user)):
    return {"email": user.email, "role": user.role}


def machine_dict(machine: MachineRow) -> dict:
    return {
        "id": machine.id,
        "name": machine.name,
        "description": machine.description,
        "status": machine.status,
        "active": machine.active,
        "last_seen": machine.last_seen,
        "created_at": machine.created_at,
    }


@router.get("/machines")
def machines(user: UserRow = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(MachineRow).order_by(MachineRow.name)
    if user.role != "manager":
        stmt = stmt.where(MachineRow.active.is_(True))
    return [machine_dict(row) for row in db.scalars(stmt).all()]


@router.post("/machines", status_code=status.HTTP_201_CREATED)
def create_machine(
    data: MachineCreate,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    if db.get(MachineRow, data.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet identifiant de machine existe déjà")
    row = MachineRow(id=data.id, name=data.name, description=data.description, status="offline", active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return machine_dict(row)


@router.put("/machines/{machine_id}")
def update_machine(
    machine_id: str,
    data: MachineUpdate,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    row = db.get(MachineRow, machine_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    row.name, row.description, row.active = data.name, data.description, data.active
    if not row.active:
        row.status = "offline"
    db.commit()
    db.refresh(row)
    return machine_dict(row)


@router.get("/machines/{machine_id}/sensors")
def list_sensors(machine_id: str, _: UserRow = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(MachineRow, machine_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    rows = db.scalars(select(SensorRow).where(SensorRow.machine_id == machine_id).order_by(SensorRow.id)).all()
    return [sensor_dict(row) for row in rows]


def sensor_dict(row: SensorRow) -> dict:
    return {
        "id": row.id,
        "machine_id": row.machine_id,
        "metric": row.metric,
        "sensor_type": row.sensor_type,
        "gpio": row.gpio,
        "unit": row.unit,
        "enabled": row.enabled,
        "created_at": row.created_at,
    }


@router.post("/machines/{machine_id}/sensors", status_code=status.HTTP_201_CREATED)
def create_sensor(
    machine_id: str,
    data: SensorCreate,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    if db.get(MachineRow, machine_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    existing = db.scalar(
        select(SensorRow).where(SensorRow.machine_id == machine_id, SensorRow.metric == data.metric)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un capteur est déjà déclaré pour cette grandeur")
    row = SensorRow(machine_id=machine_id, **data.model_dump(), enabled=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return sensor_dict(row)


@router.patch("/sensors/{sensor_id}")
def update_sensor(
    sensor_id: int,
    data: SensorUpdate,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    row = db.get(SensorRow, sensor_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capteur introuvable")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return sensor_dict(row)


@router.delete("/machines/{machine_id}", status_code=status.HTTP_200_OK)
def archive_machine(
    machine_id: str,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    row = db.get(MachineRow, machine_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    row.active, row.status = False, "offline"
    db.commit()
    return machine_dict(row)


@router.get("/machines/{machine_id}/telemetry")
def telemetry(
    machine_id: str,
    limit: int = Query(100, ge=1, le=1000),
    _: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(MeasurementRow)
        .where(MeasurementRow.machine_id == machine_id)
        .order_by(desc(MeasurementRow.recorded_at))
        .limit(limit)
    ).all()
    return [measurement_dict(row) for row in reversed(rows)]


def measurement_dict(row: MeasurementRow) -> dict:
    return {
        "id": row.id,
        "machine_id": row.machine_id,
        "seq": row.seq,
        "temperature": row.temperature,
        "humidity": row.humidity,
        "vibration_rate": row.vibration_rate,
        "vibration_edges": row.vibration_edges,
        "current_rms": row.current_rms,
        "current_source": row.current_source,
        "recorded_at": row.recorded_at,
    }


@router.get("/alerts")
def alerts(
    status_filter: Literal["new", "acknowledged", "closed"] | None = Query(None, alias="status"),
    _: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(AlertRow).order_by(desc(AlertRow.created_at)).limit(300)
    if status_filter:
        stmt = stmt.where(AlertRow.status == status_filter)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": row.id,
            "machine_id": row.machine_id,
            "metric": row.metric,
            "severity": row.severity,
            "value": row.value,
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/telemetry/{machine_id}", status_code=status.HTTP_202_ACCEPTED)
def ingest_http(
    machine_id: str,
    data: MeasurementInput,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    """Authenticated manual ingestion endpoint, intended for commissioning and tests."""
    try:
        row = SqlMeasurementRepository(db).receive(machine_id, data)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"accepted": True, "measurement_id": row.id}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(
    alert_id: int,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MAINTENANCE)),
):
    row = db.get(AlertRow, alert_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerte introuvable")
    if row.status == "new":
        row.status = "acknowledged"
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/alerts/{alert_id}/close")
def close_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MAINTENANCE)),
):
    row = db.get(AlertRow, alert_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerte introuvable")
    row.status, row.closed_at = "closed", datetime.now(timezone.utc)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/machines/{machine_id}/interventions", status_code=status.HTTP_201_CREATED)
def add_intervention(
    machine_id: str,
    data: InterventionInput,
    db: Session = Depends(get_db),
    user: UserRow = Depends(require_roles(*MAINTENANCE)),
):
    if not db.get(MachineRow, machine_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    if data.alert_id is not None:
        alert = db.get(AlertRow, data.alert_id)
        if alert is None or alert.machine_id != machine_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'alerte ne correspond pas à cette machine")
    row = InterventionRow(machine_id=machine_id, user_id=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "machine_id": row.machine_id, "description": row.description}


@router.get("/dashboard")
def dashboard(user: UserRow = Depends(current_user), db: Session = Depends(get_db)):
    machine_stmt = select(MachineRow)
    if user.role != "manager":
        machine_stmt = machine_stmt.where(MachineRow.active.is_(True))
    machines_rows = db.scalars(machine_stmt).all()
    active_alerts = db.scalars(select(AlertRow).where(AlertRow.status != "closed")).all()
    latest = db.scalars(select(MeasurementRow).order_by(desc(MeasurementRow.recorded_at)).limit(1)).first()
    return {
        "role": user.role,
        "machine_count": len(machines_rows),
        "online_count": sum(row.status == "online" for row in machines_rows),
        "active_alert_count": len(active_alerts),
        "latest": measurement_dict(latest) if latest else None,
    }


@router.get("/thresholds/{machine_id}")
def get_thresholds(machine_id: str, _: UserRow = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ThresholdRow).where(ThresholdRow.machine_id == machine_id)).all()
    return [
        {"metric": row.metric, "warning": row.warning, "critical": row.critical, "enabled": row.enabled}
        for row in rows
    ]


@router.put("/thresholds/{machine_id}/{metric}")
def set_threshold(
    machine_id: str,
    metric: str,
    data: ThresholdInput,
    db: Session = Depends(get_db),
    _: UserRow = Depends(require_roles(*MANAGERS)),
):
    if metric not in METRICS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Grandeur non reconnue")
    if data.warning >= data.critical:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le seuil critique doit dépasser l'avertissement")
    if not db.get(MachineRow, machine_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable")
    row = db.scalar(
        select(ThresholdRow).where(ThresholdRow.machine_id == machine_id, ThresholdRow.metric == metric)
    )
    if row is None:
        row = ThresholdRow(machine_id=machine_id, metric=metric, warning=data.warning, critical=data.critical)
        db.add(row)
    row.warning, row.critical, row.enabled = data.warning, data.critical, data.enabled
    db.commit()
    return {
        "machine_id": machine_id,
        "metric": metric,
        "warning": row.warning,
        "critical": row.critical,
        "enabled": row.enabled,
    }
