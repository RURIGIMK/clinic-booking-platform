import os, tempfile
import pytest
from sqlalchemy.orm import sessionmaker
dbfile = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False); dbfile.close()
os.environ["DATABASE_URL"] = "sqlite:///" + dbfile.name
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
from app.database import Base, engine, get_db
from app.main import app
from fastapi.testclient import TestClient
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)
def override_get_db():
    db=TestingSession()
    try: yield db
    finally: db.close()
app.dependency_overrides[get_db]=override_get_db
@pytest.fixture(autouse=True)
def clean_tables():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); yield
@pytest.fixture
def client():
    with TestClient(app) as c: yield c
@pytest.fixture
def seeded(client):
    from datetime import time
    from app.models import Doctor, DoctorWorkingHour, Patient
    db=TestingSession(); doctor=Doctor(name="Dr. Demo",specialty="General Practice"); patient=Patient(full_name="Patient Example")
    db.add_all([doctor,patient]); db.flush()
    for weekday in range(7): db.add(DoctorWorkingHour(doctor_id=doctor.id,weekday=weekday,opens_at=time(9),closes_at=time(17)))
    db.commit(); data={"doctor_id":doctor.id,"patient_id":patient.id}; db.close(); return data
