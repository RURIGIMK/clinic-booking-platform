from datetime import datetime, timezone, time
from sqlalchemy import DateTime, ForeignKey, Index, String, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    working_hours: Mapped[list["DoctorWorkingHour"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")

class DoctorWorkingHour(Base):
    __tablename__ = "doctor_working_hours"
    __table_args__ = (UniqueConstraint("doctor_id", "weekday", name="uq_doctor_weekday"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(nullable=False)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)
    doctor: Mapped[Doctor] = relationship(back_populates="working_hours")

class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (Index("uq_active_doctor_slot", "doctor_id", "starts_at", unique=True, postgresql_where=text("status = 'booked'"), sqlite_where=text("status = 'booked'")),)
