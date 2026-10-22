from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import settings
from app.models import Appointment, Doctor, DoctorWorkingHour, Patient

CLINIC_TZ = ZoneInfo(settings.clinic_timezone)
SLOT_MINUTES = 30

def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(422, "Datetime must include a timezone offset")
    return value.astimezone(timezone.utc)

def as_utc(value: datetime) -> datetime:
    # SQLite drops timezone metadata on DateTime values; persisted values are UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b

def session_accepts(hours: DoctorWorkingHour, local_start: datetime, local_end: datetime) -> bool:
    start_time = local_start.time().replace(tzinfo=None)
    end_time = local_end.time().replace(tzinfo=None)
    if local_end.date() != local_start.date() or start_time < hours.opens_at or end_time > hours.closes_at:
        return False
    session_start = datetime.combine(local_start.date(), hours.opens_at, tzinfo=CLINIC_TZ)
    offset_seconds = (local_start - session_start).total_seconds()
    if offset_seconds < 0 or offset_seconds % (SLOT_MINUTES * 60) != 0:
        return False
    if hours.break_starts_at and hours.break_ends_at:
        if start_time < hours.break_ends_at and end_time > hours.break_starts_at:
            return False
    return True

def validate_slot(db: Session, doctor_id: int, value: datetime, exclude_id: int | None = None):
    start = utc(value)
    end = start + timedelta(minutes=SLOT_MINUTES)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(422, "Appointment must be in the future")
    local_start = start.astimezone(CLINIC_TZ)
    local_end = end.astimezone(CLINIC_TZ)
    doctor = db.get(Doctor, doctor_id)
    if not doctor or not doctor.active:
        raise HTTPException(404, "Doctor not found")
    schedules = db.scalars(
        select(DoctorWorkingHour).where(
            DoctorWorkingHour.doctor_id == doctor_id,
            DoctorWorkingHour.weekday == local_start.weekday(),
        )
    ).all()
    if not any(session_accepts(hours, local_start, local_end) for hours in schedules):
        raise HTTPException(422, "Requested time is outside doctor working hours, overlaps a break, or is not a 30-minute slot")
    q = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status == "booked",
        Appointment.starts_at < end,
        Appointment.ends_at > start,
    )
    if exclude_id is not None:
        q = q.where(Appointment.id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, "That appointment time overlaps an existing booking")
    return start, end

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
    schedules = db.scalars(
        select(DoctorWorkingHour)
        .where(DoctorWorkingHour.doctor_id == doctor_id, DoctorWorkingHour.weekday == day.weekday())
        .order_by(DoctorWorkingHour.opens_at)
    ).all()
    if not schedules: return []

    day_start = datetime.combine(day, datetime.min.time(), tzinfo=CLINIC_TZ).astimezone(timezone.utc)
    day_end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=CLINIC_TZ).astimezone(timezone.utc)
    booked_rows = db.execute(
        select(Appointment.starts_at, Appointment.ends_at).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",
            Appointment.starts_at < day_end,
            Appointment.ends_at > day_start,
        )
    ).all()
    booked = [(as_utc(start), as_utc(end)) for start, end in booked_rows]
    now = datetime.now(timezone.utc)
    slots = []
    for hours in schedules:
        local_cursor = datetime.combine(day, hours.opens_at, tzinfo=CLINIC_TZ)
        local_closing = datetime.combine(day, hours.closes_at, tzinfo=CLINIC_TZ)
        while local_cursor + timedelta(minutes=SLOT_MINUTES) <= local_closing:
            local_end = local_cursor + timedelta(minutes=SLOT_MINUTES)
            start_utc = local_cursor.astimezone(timezone.utc)
            end_utc = local_end.astimezone(timezone.utc)
            start_time = local_cursor.time().replace(tzinfo=None)
            end_time = local_end.time().replace(tzinfo=None)
            during_break = bool(
                hours.break_starts_at and hours.break_ends_at
                and start_time < hours.break_ends_at and end_time > hours.break_starts_at
            )
            if start_utc > now and not during_break and not any(
                overlaps(start_utc, end_utc, booked_start, booked_end)
                for booked_start, booked_end in booked
            ):
                slots.append({"starts_at": start_utc, "ends_at": end_utc})
            local_cursor = local_end
    return slots
