from collections.abc import Generator
from sqlalchemy import create_engine
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
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
