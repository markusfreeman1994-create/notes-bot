
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import get_settings

class Base(DeclarativeBase):
    pass

def _engine():
    return create_engine(get_settings().DB_URL, future=True)

engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
