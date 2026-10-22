from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./clinic_booking.db"
    cors_origins: str = "http://localhost:5173"
    clinic_timezone: str = "Africa/Nairobi"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def allowed_origins(self):
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

settings = Settings()
options = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {"pool_pre_ping": True, "pool_recycle": 300}
engine = create_engine(settings.database_url, **options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class Base(DeclarativeBase):
    pass

def ensure_schema_compatibility() -> None:
    """Add nullable schedule-break columns to existing demo databases without dropping data."""
    inspector = inspect(engine)
    if "doctor_working_hours" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("doctor_working_hours")}
    with engine.begin() as connection:
        if "break_starts_at" not in columns:
            connection.execute(text("ALTER TABLE doctor_working_hours ADD COLUMN break_starts_at TIME"))
        if "break_ends_at" not in columns:
            connection.execute(text("ALTER TABLE doctor_working_hours ADD COLUMN break_ends_at TIME"))

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
