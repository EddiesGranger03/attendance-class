from datetime import date
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.session import AttendanceSession, AttendanceRecord
from app.schemas.session import SessionCreate, SessionResponse, AttendanceRecordResponse, DailyStatusResponse

router = APIRouter(prefix="/classes/{class_id}", tags=["Điểm danh & Lịch sử"])


def verify_classroom_ownership(class_id: str, user_id: str, db: Session) -> Classroom:
    classroom = db.query(Classroom).filter(
        Classroom.id == class_id,
        Classroom.teacher_id == user_id
    ).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học này."
        )
    return classroom


@router.get("/sessions", response_model=List[SessionResponse])
def get_sessions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy danh sách lịch sử tất cả các buổi điểm danh của lớp."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    sessions = db.query(AttendanceSession).filter(
        AttendanceSession.classroom_id == class_id
    ).order_by(AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc()).all()
    
    response = []
    for s in sessions:
        records_resp = [
            AttendanceRecordResponse(
                id=r.id,
                student_id=r.student_id,
                student_name_snapshot=r.student_name_snapshot,
                price_snapshot=r.price_snapshot,
                is_present=r.is_present
            ) for r in s.records
        ]
        present_count = len([r for r in s.records if r.is_present])
        response.append(SessionResponse(
            id=s.id,
            classroom_id=s.classroom_id,
            session_date=s.session_date,
            total_amount=s.total_amount,
            present_count=present_count,
            absence_reason=s.absence_reason,
            records=records_resp,
            created_at=s.created_at
        ))
    return response


@router.get("/daily/{target_date}", response_model=DailyStatusResponse)
def get_daily_attendance_status(
    class_id: str,
    target_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy trạng thái điểm danh đã lưu của một ngày cụ thể (dùng để khôi phục hoặc reset về default)."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    session = db.query(AttendanceSession).filter(
        AttendanceSession.classroom_id == class_id,
        AttendanceSession.session_date == target_date
    ).order_by(AttendanceSession.created_at.desc()).first()
    
    if not session:
        return DailyStatusResponse(
            classroom_id=class_id,
            date=target_date,
            present_student_ids=[],
            has_saved_session=False,
            session_id=None,
            total_amount=0.0
        )
        
    present_ids = [r.student_id for r in session.records if r.is_present and r.student_id is not None]
    return DailyStatusResponse(
        classroom_id=class_id,
        date=target_date,
        present_student_ids=present_ids,
        has_saved_session=True,
        session_id=session.id,
        total_amount=session.total_amount,
        absence_reason=session.absence_reason
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def record_attendance_session(
    class_id: str,
    session_in: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lưu buổi điểm danh mới (tự động tính tổng tiền dựa trên các học sinh có mặt).
    Nếu toàn bộ học sinh vắng, bắt buộc phải cung cấp lý do nghỉ (absence_reason).
    """
    verify_classroom_ownership(class_id, current_user.id, db)
    
    students = db.query(Student).filter(Student.classroom_id == class_id).all()
    if not students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học chưa có học sinh nào."
        )

    present_set = set(session_in.present_student_ids)

    # Nếu toàn bộ vắng mà không có lý do → trả lỗi
    if len(present_set) == 0 and not session_in.absence_reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Toàn bộ học sinh vắng: vui lòng nhập lý do nghỉ học."
        )

    # Optional: replace previous session on the exact same date if user is updating it
    existing_session = db.query(AttendanceSession).filter(
        AttendanceSession.classroom_id == class_id,
        AttendanceSession.session_date == session_in.session_date
    ).first()
    if existing_session:
        db.delete(existing_session)
        db.flush()
    total_amount = 0.0
    
    new_session = AttendanceSession(
        classroom_id=class_id,
        session_date=session_in.session_date,
        total_amount=0.0,
        absence_reason=session_in.absence_reason or None
    )
    db.add(new_session)
    db.flush()  # populate new_session.id
    
    records = []
    for st in students:
        is_present = st.id in present_set
        if is_present:
            total_amount += st.price_per_session

        rec = AttendanceRecord(
            session_id=new_session.id,
            student_id=st.id,
            student_name_snapshot=st.name,
            price_snapshot=st.price_per_session,
            is_present=is_present
        )
        db.add(rec)
        records.append(rec)
        
    new_session.total_amount = total_amount
    db.commit()
    db.refresh(new_session)

    records_resp = [
        AttendanceRecordResponse(
            id=r.id,
            student_id=r.student_id,
            student_name_snapshot=r.student_name_snapshot,
            price_snapshot=r.price_snapshot,
            is_present=r.is_present
        ) for r in new_session.records
    ]
    present_count = len([r for r in new_session.records if r.is_present])

    return SessionResponse(
        id=new_session.id,
        classroom_id=new_session.classroom_id,
        session_date=new_session.session_date,
        total_amount=new_session.total_amount,
        present_count=present_count,
        absence_reason=new_session.absence_reason,
        records=records_resp,
        created_at=new_session.created_at
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    class_id: str,
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa một buổi điểm danh trong lịch sử."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id,
        AttendanceSession.classroom_id == class_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy buổi điểm danh này."
        )
        
    db.delete(session)
    db.commit()
    return None
