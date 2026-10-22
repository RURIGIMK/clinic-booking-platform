import logging, time, uuid
from datetime import date, datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.booking import available_slots, cancel_appointment, create_appointment, reschedule_appointment
from app.database import Base, engine, get_db, settings, ensure_schema_compatibility
from app.models import Appointment, Doctor, Patient
from app.schemas import AppointmentCreate, AppointmentOut, CancelRequest, DoctorOut, RescheduleRequest, SlotOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinic_booking")
app = FastAPI(title="Clinic Booking API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False, allow_methods=["GET","POST","PATCH"], allow_headers=["Content-Type","X-Request-ID"])

@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    try: response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error id=%s path=%s", rid, request.url.path)
        response = JSONResponse(status_code=500, content={"detail":"An unexpected error occurred","request_id":rid})
    response.headers["X-Request-ID"] = rid
    logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.1f", rid, request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
    return response

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try: db.execute(text("SELECT 1"))
    except SQLAlchemyError: return JSONResponse(status_code=503, content={"status":"unavailable"})
    return {"status":"ready"}

@app.get("/doctors", response_model=list[DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    return list(db.scalars(select(Doctor).where(Doctor.active.is_(True)).order_by(Doctor.name)).all())

@app.get("/doctors/{doctor_id}/availability", response_model=list[SlotOut])
def doctor_availability(doctor_id: int, date: date, db: Session = Depends(get_db)):
    return available_slots(db, doctor_id, date)

@app.post("/appointments", response_model=AppointmentOut, status_code=201)
def book(payload: AppointmentCreate, db: Session = Depends(get_db)):
    return create_appointment(db, payload.doctor_id, payload.patient_id, payload.starts_at)

@app.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(appointment_id: int, payload: CancelRequest, db: Session = Depends(get_db)):
    return cancel_appointment(db, appointment_id, payload.reason)

@app.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(appointment_id: int, payload: RescheduleRequest, db: Session = Depends(get_db)):
    return reschedule_appointment(db, appointment_id, payload.starts_at)

@app.get("/patients/{patient_id}/appointments", response_model=list[AppointmentOut])
def patient_appointments(patient_id: int, db: Session = Depends(get_db)):
    if not db.get(Patient, patient_id): raise HTTPException(404, "Patient not found")
    return list(db.scalars(select(Appointment).where(Appointment.patient_id == patient_id, Appointment.status == "booked", Appointment.starts_at >= datetime.now(timezone.utc)).order_by(Appointment.starts_at)).all())
