from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from listenflow.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url, echo=settings.env == "development"
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False
        )
    return _SessionLocal


def get_db():
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
