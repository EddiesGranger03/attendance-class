from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AttendanceRecordResponse(BaseModel):
    id: str
    student_id: Optional[str]
    student_name_snapshot: str
    price_snapshot: float
    is_present: bool

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    session_date: date
    present_student_ids: List[str] = Field(default_factory=list)
    absence_reason: Optional[str] = Field(None, max_length=500)  # Bắt buộc khi 0 học sinh có mặt


class SessionResponse(BaseModel):
    id: str
    classroom_id: str
    session_date: date
    total_amount: float
    present_count: int = 0
    absence_reason: Optional[str] = None
    records: List[AttendanceRecordResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DailyStatusResponse(BaseModel):
    classroom_id: str
    date: date
    present_student_ids: List[str] = []
    has_saved_session: bool = False
    session_id: Optional[str] = None
    total_amount: float = 0.0
    absence_reason: Optional[str] = None
