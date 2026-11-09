from datetime import datetime, timezone
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.application.services import MeasurementInput
from app.infrastructure.models import AlertRow, MachineRow, MeasurementRow, ThresholdRow
from app.domain.models import Telemetry, Threshold, evaluate_thresholds


class SqlMeasurementRepository:
    def __init__(self, session: Session):
        self.session = session

    def receive(self, machine_id: str, data: MeasurementInput) -> MeasurementRow:
        machine = self.session.get(MachineRow, machine_id)
        if machine is None:
            raise LookupError("Machine non déclarée")
        if not machine.active:
            raise ValueError("Machine archivée")
        row = MeasurementRow(machine_id=machine_id, **data.model_dump(), recorded_at=datetime.now(timezone.utc))
        machine.status, machine.last_seen = "online", row.recorded_at
        self.session.add(row)
        self.session.flush()
        thresholds = self.session.scalars(select(ThresholdRow).where(ThresholdRow.machine_id == machine_id, ThresholdRow.enabled.is_(True))).all()
        readings = Telemetry(data.temperature, data.humidity, data.vibration_rate, data.vibration_edges, data.current_rms, data.current_source)
        domain_thresholds = [Threshold(t.metric, t.warning, t.critical) for t in thresholds]
        for threshold, (metric, decision) in zip(thresholds, evaluate_thresholds(readings, domain_thresholds)):
            value = decision.value
            severity = decision.severity.value if decision.severity else None
            current = self.session.scalar(select(AlertRow).where(AlertRow.machine_id == machine_id, AlertRow.metric == threshold.metric, AlertRow.status != "closed").order_by(desc(AlertRow.created_at)))
            if severity:
                if current:
                    current.severity, current.value = severity, value
                else:
                    self.session.add(AlertRow(machine_id=machine_id, metric=threshold.metric, severity=severity, value=value, status="new"))
            elif current:
                current.status, current.closed_at = "closed", datetime.now(timezone.utc)
        self.session.commit()
        return row
