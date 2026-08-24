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
    active_revenue: float = 0.0
    total_revenue: float = 0.0
    needs_settlement: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ClassroomDetailResponse(ClassroomResponse):
    average_attendance: float = 0.0
    active_session_count: int = 0
    settled_period_count: int = 0
    settlement_reminder: Optional[str] = None
