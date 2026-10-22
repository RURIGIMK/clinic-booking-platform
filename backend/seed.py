from datetime import time
from app.database import Base, SessionLocal, engine, ensure_schema_compatibility
from app.models import Doctor, DoctorWorkingHour, Patient

Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

# Representative general outpatient schedule for this demo:
# Mon-Fri 08:00-17:00 with a 12:00-13:00 lunch break; Saturday 09:00-13:00.
# Specialty sessions are narrower where that better reflects a scheduled clinic.
DOCTOR_SCHEDULES = {
    "Dr. Amina Otieno": {"specialty": "General Practice", "weekdays": range(5), "open": time(8), "close": time(17), "break_start": time(12), "break_end": time(13), "saturday": True},
    "Dr. Brian Mwangi": {"specialty": "Paediatrics", "weekdays": range(5), "open": time(8), "close": time(17), "break_start": time(12), "break_end": time(13), "saturday": True},
    "Dr. Claire Wanjiku": {"specialty": "Dermatology", "weekdays": (0, 1, 3, 4), "open": time(9), "close": time(16), "break_start": time(12), "break_end": time(13), "saturday": False},
    "Dr. David Kiptoo": {"specialty": "Family Medicine", "weekdays": range(5), "open": time(8), "close": time(17), "break_start": time(12), "break_end": time(13), "saturday": True},
    "Dr. Esther Njeri": {"specialty": "Cardiology", "weekdays": (0, 2, 4), "open": time(9), "close": time(16), "break_start": time(12), "break_end": time(13), "saturday": False},
}

with SessionLocal() as db:
    doctors = {}
    for name, schedule in DOCTOR_SCHEDULES.items():
        doctor = db.query(Doctor).filter(Doctor.name == name).one_or_none()
        if doctor is None:
            doctor = Doctor(name=name, specialty=schedule["specialty"])
            db.add(doctor)
            db.flush()
        doctor.specialty = schedule["specialty"]
        doctors[name] = doctor

    for name, schedule in DOCTOR_SCHEDULES.items():
        doctor = doctors[name]
        db.query(DoctorWorkingHour).filter(DoctorWorkingHour.doctor_id == doctor.id).delete()
        for weekday in schedule["weekdays"]:
            db.add(DoctorWorkingHour(
                doctor_id=doctor.id, weekday=weekday,
                opens_at=schedule["open"], closes_at=schedule["close"],
                break_starts_at=schedule["break_start"], break_ends_at=schedule["break_end"],
            ))
        if schedule["saturday"]:
            db.add(DoctorWorkingHour(
                doctor_id=doctor.id, weekday=5,
                opens_at=time(9), closes_at=time(13),
                break_starts_at=None, break_ends_at=None,
            ))

    if db.query(Patient).count() == 0:
        db.add_all([Patient(full_name="Alex Sample"), Patient(full_name="Jordan Example"), Patient(full_name="Taylor Demo")])
    db.commit()

print("Synthetic demo data and doctor schedules are ready.")
