import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

from urllib.parse import urlparse

DATABASE_URL = settings.DATABASE_URL
engine = None
db_fallback_error = None

def get_configured_db_host() -> str:
    try:
        parsed = urlparse(DATABASE_URL)
        return parsed.hostname or "unknown"
    except Exception:
        return "unknown"

def _get_sqlite_url() -> str:
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "attendance.db")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "database", "attendance.db")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database", "attendance.db")),
        os.path.abspath("database/attendance.db"),
        os.path.abspath("attendance.db")
    ]
    for c in candidates:
        if os.path.exists(c):
            return f"sqlite:///{c.replace(os.sep, '/')}"
    # If not found yet, default to database/attendance.db in workspace root
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "database"))
    os.makedirs(db_dir, exist_ok=True)
    target_file = os.path.join(db_dir, "attendance.db")
    return f"sqlite:///{target_file.replace(os.sep, '/')}"

def _normalize_postgres_url(url: str) -> str:
    """Ensure SQLAlchemy uses psycopg2 driver (installed via psycopg2-binary) even on SQLAlchemy 2.1+."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return url

# Attempt to connect to PostgreSQL; if fallback is enabled and connection fails, use SQLite
try:
    if DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres://"):
        normalized_db_url = _normalize_postgres_url(DATABASE_URL)
        # Test engine creation with connect_timeout so unreachable DB hosts don't hang startup
        engine = create_engine(
            normalized_db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10}
        )
        # Test connection
        with engine.connect() as conn:
            pass
        db_fallback_error = None
except Exception as e:
    engine = None
    db_fallback_error = str(e)
    if settings.USE_SQLITE_FALLBACK:
        SQLITE_URL = _get_sqlite_url()
        print(f"[DATABASE NOTICE] PostgreSQL connection failed ({e}). Falling back to local SQLite: '{SQLITE_URL}'.")
        engine = create_engine(
            SQLITE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        # Fail fast: refuse to start rather than serve an empty/temporary database.
        # On Render a failed start keeps the previous healthy deploy running.
        raise RuntimeError(
            f"Cannot connect to the configured database (host: {get_configured_db_host()}). "
            f"Refusing to start so no empty fallback database is used. Original error: {e}"
        ) from e

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
