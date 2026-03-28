from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_engine(
    settings.jobs_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.jobs_database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class JobsBase(DeclarativeBase):
    pass


def get_jobs_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
