import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from sqlalchemy import text
import app.models  # Ensure all models are registered with Base.metadata
from app.core.config import settings
from app.core.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.classrooms import router as classrooms_router
from app.routers.students import router as students_router
from app.routers.sessions import router as sessions_router

# Create tables immediately on startup
Base.metadata.create_all(bind=engine)

def auto_migrate():
    """Ensure newly added columns exist in database."""
    with engine.connect() as conn:
        # Migrate students columns
        for col, col_type in [
            ("school_class", "VARCHAR(100)"),
            ("school_name", "VARCHAR(255)"),
            ("parent_phone", "VARCHAR(50)")
        ]:
            try:
                if engine.dialect.name == "postgresql":
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                elif engine.dialect.name == "sqlite":
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN {col} {col_type};"))
                conn.commit()
            except Exception:
                pass

        # Migrate attendance_sessions columns
        try:
            if engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN IF NOT EXISTS absence_reason VARCHAR(500);"))
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN IF NOT EXISTS period_id VARCHAR(36);"))
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN IF NOT EXISTS is_settled BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS note VARCHAR(500);"))
                conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS notes VARCHAR(1000);"))
            elif engine.dialect.name == "sqlite":
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN absence_reason VARCHAR(500);"))
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN period_id VARCHAR(36);"))
                conn.execute(text("ALTER TABLE attendance_sessions ADD COLUMN is_settled BOOLEAN DEFAULT 0;"))
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN note VARCHAR(500);"))
                conn.execute(text("ALTER TABLE students ADD COLUMN notes VARCHAR(1000);"))
            conn.commit()
        except Exception:
            pass

auto_migrate()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    auto_migrate()
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
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
