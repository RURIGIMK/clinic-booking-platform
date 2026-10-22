from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class DoctorOut(BaseModel):
    id: int
    name: str
    specialty: str
    model_config = ConfigDict(from_attributes=True)

class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    starts_at: datetime
    @field_validator("starts_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError("starts_at must include a timezone offset")
        return value

class AppointmentOut(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    cancellation_reason: str | None = None
    model_config = ConfigDict(from_attributes=True)

class CancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

class RescheduleRequest(BaseModel):
    starts_at: datetime
    @field_validator("starts_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError("starts_at must include a timezone offset")
        return value

class SlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime
