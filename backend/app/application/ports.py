from typing import Protocol
from .services import MeasurementInput


class MeasurementRepository(Protocol):
    def save_measurement(self, machine_id: str, data: MeasurementInput): ...
    def evaluate_and_store_alerts(self, machine_id: str, data: MeasurementInput): ...
