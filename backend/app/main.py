import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import Request

from sqlalchemy import inspect, text
import app.models  # Ensure all models are registered with Base.metadata
from app.core.config import settings
from app.core.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.classrooms import router as classrooms_router
from app.routers.students import router as students_router
from app.routers.sessions import router as sessions_router

logger = logging.getLogger("app.migrate")
HEALTH_TABLES = ("users", "classrooms", "students", "attendance_sessions", "attendance_records")

# (table, column, type for postgres, type for sqlite). Additive-only: never drop/rename here.
MIGRATION_COLUMNS = [
    ("students", "school_class", "VARCHAR(100)", "VARCHAR(100)"),
    ("students", "school_name", "VARCHAR(255)", "VARCHAR(255)"),
    ("students", "parent_phone", "VARCHAR(50)", "VARCHAR(50)"),
    ("students", "notes", "VARCHAR(1000)", "VARCHAR(1000)"),
    ("attendance_sessions", "absence_reason", "VARCHAR(500)", "VARCHAR(500)"),
    ("attendance_sessions", "period_id", "VARCHAR(36)", "VARCHAR(36)"),
    ("attendance_sessions", "is_settled", "BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
    ("attendance_records", "note", "VARCHAR(500)", "VARCHAR(500)"),
]


def auto_migrate():
    """Add any missing columns. Additive only; errors are logged, never silently swallowed."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, col, pg_type, sqlite_type in MIGRATION_COLUMNS:
        if table not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table)}
        if col in have:
            continue
        col_type = pg_type if engine.dialect.name == "postgresql" else sqlite_type
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
            logger.warning("Migration: added column %s.%s", table, col)
        except Exception:
            logger.exception("Migration FAILED: could not add column %s.%s", table, col)


def run_startup_tasks():
    Base.metadata.create_all(bind=engine)  # only creates missing tables, never drops
    auto_migrate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_startup_tasks()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hệ thống Quản lý & Điểm danh Lớp học dành riêng cho Giáo viên",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

@app.middleware("http")
async def maintenance_guard(request: Request, call_next):
    """Return 503 for API calls while MAINTENANCE_MODE is on. /health stays reachable."""
    path = request.url.path
    if (
        settings.MAINTENANCE_MODE
        and path.startswith(settings.API_V1_STR)
        and path != f"{settings.API_V1_STR}/health"
        and request.method != "OPTIONS"
    ):
        return JSONResponse(
            status_code=503,
            content={"maintenance": True, "detail": "Hệ thống đang bảo trì. Dữ liệu của bạn được giữ an toàn."},
            headers={"Retry-After": "30"},
        )
    return await call_next(request)


# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(classrooms_router, prefix=settings.API_V1_STR)
app.include_router(students_router, prefix=settings.API_V1_STR)
app.include_router(sessions_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    # If the HTML frontend file exists in front-end directory or parent directories, serve it
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "front-end", "diem-danh-lop-hoc.html")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "front-end", "diem-danh-lop-hoc.html")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "diem-danh-lop-hoc.html")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "diem-danh-lop-hoc.html")),
        "/app/front-end/diem-danh-lop-hoc.html",
        "/app/diem-danh-lop-hoc.html"
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/html")
    return {
        "message": "Sổ Điểm Danh API đang hoạt động.",
        "docs_url": "/docs",
        "version": "1.0.0"
    }


@app.get("/logo.png", tags=["Assets"])
@app.get("/image/logo.png", tags=["Assets"])
def get_logo():
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "image", "logo.png")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "image", "logo.png")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logo.png")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logo.png")),
        "/app/image/logo.png",
        "/app/logo.png"
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/png")
    return {"error": "Logo not found"}


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check(request: Request):
    """Deep health: pings the DB and reports row counts so an unexpectedly empty DB is obvious."""
    counts = {}
    show_counts = bool(settings.HEALTH_TOKEN) and request.headers.get("x-health-token") == settings.HEALTH_TOKEN
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            for table in (HEALTH_TABLES if show_counts else ()):
                counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        db_ok = True
    except Exception as e:
        logging.getLogger("app.health").exception("Health check DB error")
        db_ok = False
        counts = {"error": type(e).__name__}
    body = {
        "status": "ok" if db_ok else "degraded",
        "project": settings.PROJECT_NAME,
        "db_dialect": engine.dialect.name if engine else "none",
        "maintenance": settings.MAINTENANCE_MODE,
        "counts": counts,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
