import uuid
from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.core.database import Base


class RevenuePeriod(Base):
    __tablename__ = "revenue_periods"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id = Column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    period_name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    total_revenue = Column(Float, nullable=False, default=0.0)
    session_count = Column(Integer, nullable=False, default=0)
    total_present = Column(Integer, nullable=False, default=0)
    closed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(String(500), nullable=True)

    # Relationships
    classroom = relationship("Classroom", back_populates="revenue_periods")
    sessions = relationship("AttendanceSession", back_populates="revenue_period")


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id = Column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date = Column(Date, nullable=False, index=True)
    total_amount = Column(Float, nullable=False, default=0.0)
    absence_reason = Column(String(500), nullable=True, default=None)  # Lý do nghỉ khi toàn lớp vắng
    period_id = Column(String(36), ForeignKey("revenue_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    is_settled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    classroom = relationship("Classroom", back_populates="sessions")
    records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    revenue_period = relationship("RevenuePeriod", back_populates="sessions")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    student_name_snapshot = Column(String(255), nullable=False)
    price_snapshot = Column(Float, nullable=False, default=0.0)
    is_present = Column(Boolean, nullable=False, default=False)

    # Relationships
    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("Student", back_populates="attendance_records")
