from datetime import date
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.session import AttendanceSession, RevenuePeriod
from app.schemas.classroom import ClassroomCreate, ClassroomUpdate, ClassroomResponse, ClassroomDetailResponse

router = APIRouter(prefix="/classes", tags=["Quản lý Lớp học"])


@router.get("", response_model=List[ClassroomResponse])
def get_classrooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy toàn bộ danh sách lớp học của giáo viên hiện tại kèm doanh thu kỳ hiện tại & tổng doanh thu."""
    classrooms = db.query(Classroom).filter(Classroom.teacher_id == current_user.id).order_by(Classroom.created_at.desc()).all()
    today = date.today()
    is_settlement_time = today.day >= 2
    
    result = []
    for c in classrooms:
        student_count = db.query(func.count(Student.id)).filter(Student.classroom_id == c.id).scalar() or 0
        session_count = db.query(func.count(AttendanceSession.id)).filter(AttendanceSession.classroom_id == c.id).scalar() or 0
        
        # Doanh thu kỳ hiện tại (chưa chốt)
        active_revenue = db.query(func.coalesce(func.sum(AttendanceSession.total_amount), 0.0)).filter(
            AttendanceSession.classroom_id == c.id,
            AttendanceSession.is_settled == False
        ).scalar() or 0.0
        
        # Tổng doanh thu tích lũy toàn thời gian
        total_revenue = db.query(func.coalesce(func.sum(AttendanceSession.total_amount), 0.0)).filter(
            AttendanceSession.classroom_id == c.id
        ).scalar() or 0.0

        unsettled_count = db.query(func.count(AttendanceSession.id)).filter(
            AttendanceSession.classroom_id == c.id,
            AttendanceSession.is_settled == False
        ).scalar() or 0
        
        needs_settlement = bool(is_settlement_time and unsettled_count > 0)

        result.append(ClassroomResponse(
            id=c.id,
            teacher_id=c.teacher_id,
            name=c.name,
            student_count=student_count,
            session_count=session_count,
            active_revenue=float(active_revenue),
            total_revenue=float(total_revenue),
            needs_settlement=needs_settlement,
            created_at=c.created_at
        ))
    return result


@router.post("", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
def create_classroom(
    classroom_in: ClassroomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Tạo lớp học mới cho giáo viên."""
    new_classroom = Classroom(
        teacher_id=current_user.id,
        name=classroom_in.name.strip()
    )
    db.add(new_classroom)
    db.commit()
    db.refresh(new_classroom)
    
    return ClassroomResponse(
        id=new_classroom.id,
        teacher_id=new_classroom.teacher_id,
        name=new_classroom.name,
        student_count=0,
        session_count=0,
        active_revenue=0.0,
        total_revenue=0.0,
        needs_settlement=False,
        created_at=new_classroom.created_at
    )


@router.get("/{class_id}", response_model=ClassroomDetailResponse)
def get_classroom_detail(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy chi tiết lớp học kèm các thống kê (doanh thu kỳ hiện tại, tổng doanh thu, kỳ đã chốt)."""
    classroom = db.query(Classroom).filter(
        Classroom.id == class_id,
        Classroom.teacher_id == current_user.id
    ).first()
    
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học này."
        )

    student_count = db.query(func.count(Student.id)).filter(Student.classroom_id == classroom.id).scalar() or 0
    sessions = db.query(AttendanceSession).filter(AttendanceSession.classroom_id == classroom.id).all()
    session_count = len(sessions)
    
    # Active sessions (unsettled)
    active_sessions = [s for s in sessions if not s.is_settled]
    active_session_count = len(active_sessions)
    active_revenue = sum(s.total_amount for s in active_sessions)
    total_revenue = sum(s.total_amount for s in sessions)
    
    settled_period_count = db.query(func.count(RevenuePeriod.id)).filter(RevenuePeriod.classroom_id == classroom.id).scalar() or 0

    # Calculate average attendance per session
    total_present = 0
    for s in sessions:
        total_present += len([r for r in s.records if r.is_present])
    avg_attendance = round(total_present / session_count, 1) if session_count > 0 else 0.0

    today = date.today()
    is_settlement_time = today.day >= 2
    needs_settlement = bool(is_settlement_time and active_session_count > 0)
    reminder = "Đã đến kỳ chốt doanh thu tháng (ngày mùng 2)! Vui lòng Xuất PDF báo cáo & Chốt kỳ doanh thu." if needs_settlement else None

    return ClassroomDetailResponse(
        id=classroom.id,
        teacher_id=classroom.teacher_id,
        name=classroom.name,
        student_count=student_count,
        session_count=session_count,
        active_session_count=active_session_count,
        settled_period_count=settled_period_count,
        active_revenue=float(active_revenue),
        total_revenue=float(total_revenue),
        needs_settlement=needs_settlement,
        settlement_reminder=reminder,
        average_attendance=avg_attendance,
        created_at=classroom.created_at
    )


@router.put("/{class_id}", response_model=ClassroomResponse)
def update_classroom(
    class_id: str,
    classroom_in: ClassroomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Cập nhật tên lớp học."""
    classroom = db.query(Classroom).filter(
        Classroom.id == class_id,
        Classroom.teacher_id == current_user.id
    ).first()
    
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học này."
        )

    if classroom_in.name:
        classroom.name = classroom_in.name.strip()
        db.commit()
        db.refresh(classroom)

    student_count = db.query(func.count(Student.id)).filter(Student.classroom_id == classroom.id).scalar() or 0
    session_count = db.query(func.count(AttendanceSession.id)).filter(AttendanceSession.classroom_id == classroom.id).scalar() or 0

    return ClassroomResponse(
        id=classroom.id,
        teacher_id=classroom.teacher_id,
        name=classroom.name,
        student_count=student_count,
        session_count=session_count,
        created_at=classroom.created_at
    )


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_classroom(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa lớp học (toàn bộ học sinh và lịch sử điểm danh sẽ bị xóa tự động)."""
    classroom = db.query(Classroom).filter(
        Classroom.id == class_id,
        Classroom.teacher_id == current_user.id
    ).first()
    
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học này."
        )

    db.delete(classroom)
    db.commit()
    return None
