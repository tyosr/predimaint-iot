from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class MeasurementInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    seq: int = Field(ge=0)
    temperature: float = Field(ge=-40, le=125)
    humidity: float = Field(ge=0, le=100)
    vibration_rate: float = Field(ge=0, le=10000)
    vibration_edges: int = Field(ge=0, le=1000000)
    current_rms: float = Field(ge=0, le=1000)
    current_source: str = Field(default="simulated", max_length=20)


def timestamp_measurement(data: MeasurementInput) -> dict:
    return {**data.model_dump(), "recorded_at": datetime.now(timezone.utc)}
