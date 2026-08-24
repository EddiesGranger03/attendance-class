from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ClassroomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class ClassroomResponse(BaseModel):
    id: str
    teacher_id: str
    name: str
    student_count: int = 0
    session_count: int = 0
    total_revenue: float = 0.0
    created_at: datetime

    class Config:
        from_attributes = True


class ClassroomDetailResponse(ClassroomResponse):
    total_revenue: float = 0.0
    average_attendance: float = 0.0
