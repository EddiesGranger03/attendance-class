from app.routers.auth import router as auth_router
from app.routers.classrooms import router as classrooms_router
from app.routers.students import router as students_router
from app.routers.sessions import router as sessions_router

__all__ = ["auth_router", "classrooms_router", "students_router", "sessions_router"]
