from datetime import time
from app.database import Base, SessionLocal, engine
from app.models import Doctor, DoctorWorkingHour, Patient
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    if db.query(Doctor).count() == 0:
        doctors = [Doctor(name="Dr. Amina Otieno", specialty="General Practice"), Doctor(name="Dr. Brian Mwangi", specialty="Paediatrics"), Doctor(name="Dr. Claire Wanjiku", specialty="Dermatology"), Doctor(name="Dr. David Kiptoo", specialty="Family Medicine"), Doctor(name="Dr. Esther Njeri", specialty="Cardiology")]
        db.add_all(doctors); db.flush()
        for doctor in doctors:
            for weekday in range(5):
                db.add(DoctorWorkingHour(doctor_id=doctor.id, weekday=weekday, opens_at=time(9), closes_at=time(17)))
    if db.query(Patient).count() == 0:
        db.add_all([Patient(full_name="Alex Sample"), Patient(full_name="Jordan Example"), Patient(full_name="Taylor Demo")])
    db.commit()
print("Synthetic demo data is ready.")
