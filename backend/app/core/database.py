import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL
engine = None

# Attempt to connect to PostgreSQL; if fallback is enabled and connection fails, use SQLite
try:
    if DATABASE_URL.startswith("postgresql"):
        # Test engine creation
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        # Test connection
        with engine.connect() as conn:
            pass
except Exception as e:
    if settings.USE_SQLITE_FALLBACK:
        print(f"[DATABASE NOTICE] PostgreSQL connection failed ({e}). Falling back to local SQLite: 'attendance.db'.")
        SQLITE_URL = "sqlite:///./attendance.db"
        engine = create_engine(
            SQLITE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        raise e

if engine is None:
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for obtaining a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
