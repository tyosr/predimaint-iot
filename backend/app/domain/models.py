from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    TECHNICIAN = "technician"
    MANAGER = "manager"
    DIRECTOR = "director"


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Telemetry:
    temperature: float
    humidity: float
    vibration_rate: float
    vibration_edges: int
    current_rms: float
    current_source: str = "simulated"


@dataclass(frozen=True)
class Threshold:
    metric: str
    warning: float
    critical: float


@dataclass(frozen=True)
class AlertDecision:
    severity: Severity | None
    value: float | None


def evaluate_thresholds(measurement: Telemetry, thresholds: list[Threshold]) -> list[tuple[str, AlertDecision]]:
    decisions = []
    for threshold in thresholds:
        value = getattr(measurement, threshold.metric)
        severity = Severity.CRITICAL if value >= threshold.critical else Severity.WARNING if value >= threshold.warning else None
        decisions.append((threshold.metric, AlertDecision(severity, value if severity else None)))
    return decisions


def utc_now() -> datetime:
    return datetime.utcnow()
