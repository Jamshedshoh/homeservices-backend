from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_engine(
    settings.messaging_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.messaging_database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MessagingBase(DeclarativeBase):
    pass


def get_messaging_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
