from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import settings
from app.models import Appointment, Doctor, DoctorWorkingHour, Patient

CLINIC_TZ = ZoneInfo(settings.clinic_timezone)

def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(422, "Datetime must include a timezone offset")
    return value.astimezone(timezone.utc)

def validate_slot(db: Session, doctor_id: int, value: datetime, exclude_id: int | None = None):
    start = utc(value)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(422, "Appointment must be in the future")
    local_start = start.astimezone(CLINIC_TZ)
    local_end = (start + timedelta(minutes=30)).astimezone(CLINIC_TZ)
    doctor = db.get(Doctor, doctor_id)
    if not doctor or not doctor.active:
        raise HTTPException(404, "Doctor not found")
    hours = db.scalar(select(DoctorWorkingHour).where(DoctorWorkingHour.doctor_id == doctor_id, DoctorWorkingHour.weekday == local_start.weekday()))
    if not hours or local_start.time().replace(tzinfo=None) < hours.opens_at or local_end.time().replace(tzinfo=None) > hours.closes_at or local_end.date() != local_start.date():
        raise HTTPException(422, "Requested slot is outside doctor working hours")
    q = select(Appointment).where(Appointment.doctor_id == doctor_id, Appointment.starts_at == start, Appointment.status == "booked")
    if exclude_id is not None:
        q = q.where(Appointment.id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, "That appointment slot is no longer available")
    return start, start + timedelta(minutes=30)

def create_appointment(db: Session, doctor_id: int, patient_id: int, starts_at: datetime):
    if not db.get(Patient, patient_id):
        raise HTTPException(404, "Patient not found")
    start, end = validate_slot(db, doctor_id, starts_at)
    item = Appointment(doctor_id=doctor_id, patient_id=patient_id, starts_at=start, ends_at=end)
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That appointment slot was just booked") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Booking service temporarily unavailable") from exc
    return item

def cancel_appointment(db: Session, appointment_id: int, reason: str):
    item = db.get(Appointment, appointment_id)
    if not item: raise HTTPException(404, "Appointment not found")
    if item.status == "cancelled": raise HTTPException(409, "Appointment is already cancelled")
    item.status, item.cancellation_reason = "cancelled", reason.strip()
    try:
        db.commit(); db.refresh(item)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Cancellation service temporarily unavailable") from exc
    return item

def reschedule_appointment(db: Session, appointment_id: int, starts_at: datetime):
    item = db.get(Appointment, appointment_id)
    if not item: raise HTTPException(404, "Appointment not found")
    if item.status == "cancelled": raise HTTPException(409, "Cancelled appointments cannot be rescheduled")
    start, end = validate_slot(db, item.doctor_id, starts_at, item.id)
    item.starts_at, item.ends_at = start, end
    try:
        db.commit(); db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That appointment slot was just booked") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Rescheduling service temporarily unavailable") from exc
    return item

def available_slots(db: Session, doctor_id: int, day: date):
    doctor = db.get(Doctor, doctor_id)
    if not doctor or not doctor.active: raise HTTPException(404, "Doctor not found")
    hours = db.scalar(select(DoctorWorkingHour).where(DoctorWorkingHour.doctor_id == doctor_id, DoctorWorkingHour.weekday == day.weekday()))
    if not hours: return []
    local_cursor = datetime.combine(day, hours.opens_at, tzinfo=CLINIC_TZ)
    local_closing = datetime.combine(day, hours.closes_at, tzinfo=CLINIC_TZ)
    utc_open = local_cursor.astimezone(timezone.utc)
    utc_close = local_closing.astimezone(timezone.utc)
    booked_values = db.scalars(select(Appointment.starts_at).where(Appointment.doctor_id == doctor_id, Appointment.status == "booked", Appointment.starts_at >= utc_open, Appointment.starts_at < utc_close)).all()
    booked = {value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc) for value in booked_values}
    slots = []
    while local_cursor + timedelta(minutes=30) <= local_closing:
        local_end = local_cursor + timedelta(minutes=30)
        start_utc = local_cursor.astimezone(timezone.utc)
        end_utc = local_end.astimezone(timezone.utc)
        if start_utc > datetime.now(timezone.utc) and start_utc not in booked:
            slots.append({"starts_at": start_utc, "ends_at": end_utc})
        local_cursor = local_end
    return slots
