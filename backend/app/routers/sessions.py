from datetime import date, datetime, timezone
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.session import AttendanceSession, AttendanceRecord, RevenuePeriod
from app.schemas.session import (
    SessionCreate,
    SessionResponse,
    AttendanceRecordResponse,
    DailyStatusResponse,
    RevenuePeriodCloseRequest,
    RevenuePeriodResponse,
    RevenuePeriodDetailResponse,
    RevenueStatusResponse
)

router = APIRouter(prefix="/classes/{class_id}", tags=["Điểm danh & Doanh thu"])


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
    period_id: Optional[str] = None,
    unsettled_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy danh sách lịch sử các buổi điểm danh của lớp (hỗ trợ lọc theo kỳ hoặc chỉ các buổi chưa chốt)."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    query = db.query(AttendanceSession).filter(AttendanceSession.classroom_id == class_id)
    if period_id:
        query = query.filter(AttendanceSession.period_id == period_id)
    elif unsettled_only:
        query = query.filter(AttendanceSession.is_settled == False)

    sessions = query.order_by(AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc()).all()
    
    response = []
    for s in sessions:
        records_resp = [
            AttendanceRecordResponse(
                id=r.id,
                student_id=r.student_id,
                student_name_snapshot=r.student_name_snapshot,
                price_snapshot=r.price_snapshot,
                is_present=r.is_present,
                note=r.note
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
            period_id=s.period_id,
            is_settled=s.is_settled,
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
    """Lấy trạng thái điểm danh đã lưu của một ngày cụ thể (kèm ghi chú học sinh)."""
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
            student_notes={},
            has_saved_session=False,
            session_id=None,
            total_amount=0.0
        )
        
    present_ids = [r.student_id for r in session.records if r.is_present and r.student_id is not None]
    student_notes = {r.student_id: r.note for r in session.records if r.student_id is not None and r.note}
    return DailyStatusResponse(
        classroom_id=class_id,
        date=target_date,
        present_student_ids=present_ids,
        student_notes=student_notes,
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
    """Lưu buổi điểm danh mới (tự động tính tổng tiền và lưu ghi chú từng học sinh)."""
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

    # Replace previous session on the exact same date if user is updating it
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
        absence_reason=session_in.absence_reason or None,
        period_id=None,
        is_settled=False
    )
    db.add(new_session)
    db.flush()  # populate new_session.id
    
    student_notes_in = session_in.student_notes or {}
    records = []
    for st in students:
        is_present = st.id in present_set
        st_note = student_notes_in.get(st.id)
        if st_note:
            st_note = st_note.strip() or None
        else:
            st_note = None

        if is_present:
            total_amount += st.price_per_session

        rec = AttendanceRecord(
            session_id=new_session.id,
            student_id=st.id,
            student_name_snapshot=st.name,
            price_snapshot=st.price_per_session,
            is_present=is_present,
            note=st_note
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
            is_present=r.is_present,
            note=r.note
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
        period_id=new_session.period_id,
        is_settled=new_session.is_settled,
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


# =========================================================================
# CHU KỲ DOANH THU & CHỐT SỔ (Monthly Revenue Settlement & Period History)
# =========================================================================

@router.get("/revenue-status", response_model=RevenueStatusResponse)
def get_revenue_status(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Kiểm tra tình trạng doanh thu kỳ hiện tại & thông báo nhắc nhở chốt sổ ngày mùng 2."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    unsettled_sessions = db.query(AttendanceSession).filter(
        AttendanceSession.classroom_id == class_id,
        AttendanceSession.is_settled == False
    ).order_by(AttendanceSession.session_date.asc()).all()
    
    active_revenue = sum(s.total_amount for s in unsettled_sessions)
    active_count = len(unsettled_sessions)
    
    total_historical = db.query(func.coalesce(func.sum(AttendanceSession.total_amount), 0.0)).filter(
        AttendanceSession.classroom_id == class_id
    ).scalar() or 0.0
    
    earliest_date = unsettled_sessions[0].session_date if unsettled_sessions else None
    latest_date = unsettled_sessions[-1].session_date if unsettled_sessions else None
    
    today = date.today()
    is_settlement_time = today.day >= 2
    needs_settlement = bool(is_settlement_time and active_count > 0)
    reminder = f"Đã đến kỳ chốt doanh thu tháng! Lớp này đang có {active_count} buổi học chưa chốt (Tổng: {active_revenue:,.0f}₫). Vui lòng Xuất PDF báo cáo & Chốt kỳ doanh thu." if needs_settlement else None
    
    return RevenueStatusResponse(
        classroom_id=class_id,
        current_active_revenue=float(active_revenue),
        current_active_session_count=active_count,
        total_historical_revenue=float(total_historical),
        earliest_unsettled_date=earliest_date,
        latest_unsettled_date=latest_date,
        needs_settlement=needs_settlement,
        reminder_message=reminder
    )


@router.get("/revenue-periods", response_model=List[RevenuePeriodResponse])
def get_revenue_periods(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy danh sách toàn bộ các kỳ doanh thu đã chốt trong lịch sử của lớp."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    periods = db.query(RevenuePeriod).filter(
        RevenuePeriod.classroom_id == class_id
    ).order_by(RevenuePeriod.closed_at.desc()).all()
    return periods


@router.post("/revenue-periods/close", response_model=RevenuePeriodResponse, status_code=status.HTTP_201_CREATED)
def close_revenue_period(
    class_id: str,
    req: RevenuePeriodCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Thực hiện xuất báo cáo & Chốt kỳ doanh thu hiện tại (đóng kỳ, lưu vào lịch sử, reset doanh thu kỳ mới về 0₫)."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    unsettled_sessions = db.query(AttendanceSession).filter(
        AttendanceSession.classroom_id == class_id,
        AttendanceSession.is_settled == False
    ).order_by(AttendanceSession.session_date.asc()).all()
    
    if not unsettled_sessions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không có buổi học nào chưa chốt trong kỳ này để tạo báo cáo chốt doanh thu."
        )
        
    start_date = unsettled_sessions[0].session_date
    end_date = unsettled_sessions[-1].session_date
    total_revenue = sum(s.total_amount for s in unsettled_sessions)
    session_count = len(unsettled_sessions)
    
    total_present = 0
    for s in unsettled_sessions:
        total_present += len([r for r in s.records if r.is_present])
        
    # Default name if not provided
    period_name = req.period_name.strip() if (req.period_name and req.period_name.strip()) else f"Kỳ Tháng {end_date.strftime('%m/%Y')}"
    
    new_period = RevenuePeriod(
        classroom_id=class_id,
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        total_revenue=float(total_revenue),
        session_count=session_count,
        total_present=total_present,
        closed_at=datetime.now(timezone.utc),
        notes=req.notes
    )
    db.add(new_period)
    db.flush()
    
    # Mark all active sessions as settled and attach to new_period
    for s in unsettled_sessions:
        s.period_id = new_period.id
        s.is_settled = True
        
    db.commit()
    db.refresh(new_period)
    return new_period


@router.get("/revenue-periods/{period_id}", response_model=RevenuePeriodDetailResponse)
def get_revenue_period_detail(
    class_id: str,
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy thông tin chi tiết và danh sách buổi học của một kỳ đã chốt (để xuất lại PDF)."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    period = db.query(RevenuePeriod).filter(
        RevenuePeriod.id == period_id,
        RevenuePeriod.classroom_id == class_id
    ).first()
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỳ doanh thu này."
        )
        
    sessions = db.query(AttendanceSession).filter(
        AttendanceSession.period_id == period.id
    ).order_by(AttendanceSession.session_date.asc()).all()
    
    session_responses = []
    for s in sessions:
        records_resp = [
            AttendanceRecordResponse(
                id=r.id,
                student_id=r.student_id,
                student_name_snapshot=r.student_name_snapshot,
                price_snapshot=r.price_snapshot,
                is_present=r.is_present,
                note=r.note
            ) for r in s.records
        ]
        session_responses.append(SessionResponse(
            id=s.id,
            classroom_id=s.classroom_id,
            session_date=s.session_date,
            total_amount=s.total_amount,
            present_count=len([r for r in s.records if r.is_present]),
            absence_reason=s.absence_reason,
            period_id=s.period_id,
            is_settled=s.is_settled,
            records=records_resp,
            created_at=s.created_at
        ))
        
    return RevenuePeriodDetailResponse(
        id=period.id,
        classroom_id=period.classroom_id,
        period_name=period.period_name,
        start_date=period.start_date,
        end_date=period.end_date,
        total_revenue=period.total_revenue,
        session_count=period.session_count,
        total_present=period.total_present,
        closed_at=period.closed_at,
        notes=period.notes,
        sessions=session_responses
    )


@router.post("/revenue-periods/{period_id}/reopen")
def reopen_revenue_period(
    class_id: str,
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Hoàn tác (Undo) mở lại kỳ doanh thu đã chốt nếu lỡ ấn nhầm (đưa các buổi học trở lại kỳ hiện tại)."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    period = db.query(RevenuePeriod).filter(
        RevenuePeriod.id == period_id,
        RevenuePeriod.classroom_id == class_id
    ).first()
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỳ doanh thu này."
        )
        
    # Unlink sessions
    sessions = db.query(AttendanceSession).filter(AttendanceSession.period_id == period.id).all()
    for s in sessions:
        s.period_id = None
        s.is_settled = False
        
    db.delete(period)
    db.commit()
    
    return {
        "message": f"Đã hoàn tác và mở lại kỳ '{period.period_name}' thành công. Các buổi học đã được trả về kỳ hiện tại.",
        "reopened_session_count": len(sessions)
    }
