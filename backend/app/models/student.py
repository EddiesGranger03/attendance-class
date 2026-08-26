import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id = Column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    school_class = Column(String(100), nullable=True)
    school_name = Column(String(255), nullable=True)
    parent_phone = Column(String(50), nullable=True)
    price_per_session = Column(Float, nullable=False, default=0.0)
    notes = Column(String(1000), nullable=True, default=None)  # Ghi chú / Lưu ý chung của Trợ Lý & Giáo Viên
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    classroom = relationship("Classroom", back_populates="students")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
