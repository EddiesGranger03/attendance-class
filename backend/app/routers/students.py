from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.classroom import Classroom
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse

router = APIRouter(prefix="/classes/{class_id}/students", tags=["Quản lý Học sinh"])


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


@router.get("", response_model=List[StudentResponse])
def get_students(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Lấy danh sách học sinh trong một lớp học."""
    verify_classroom_ownership(class_id, current_user.id, db)
    students = db.query(Student).filter(Student.classroom_id == class_id).order_by(Student.created_at.asc()).all()
    return students


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def add_student(
    class_id: str,
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Thêm học sinh mới vào lớp."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    clean_name = student_in.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên học sinh không được để trống."
        )
    
    # Kiểm tra trùng tên học sinh trong cùng 1 lớp (không phân biệt hoa/thường)
    duplicate_exists = db.query(Student).filter(
        Student.classroom_id == class_id,
        func.lower(Student.name) == clean_name.lower()
    ).first()
    if duplicate_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lớp đã có học sinh tên '{clean_name}'. Vui lòng thêm họ, tên đệm hoặc ký hiệu phân biệt để tránh trùng tên!"
        )
    
    new_student = Student(
        classroom_id=class_id,
        name=clean_name,
        school_class=student_in.school_class.strip() if student_in.school_class else None,
        school_name=student_in.school_name.strip() if student_in.school_name else None,
        parent_phone=student_in.parent_phone.strip() if student_in.parent_phone else None,
        price_per_session=float(student_in.price_per_session)
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    class_id: str,
    student_id: str,
    student_in: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Cập nhật thông tin (tên, lớp, trường, SĐT, học phí) của học sinh."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.classroom_id == class_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học sinh này."
        )
        
    if student_in.name is not None:
        clean_name = student_in.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên học sinh không được để trống."
            )
        # Kiểm tra trùng tên với học sinh khác trong cùng 1 lớp
        duplicate_exists = db.query(Student).filter(
            Student.classroom_id == class_id,
            Student.id != student_id,
            func.lower(Student.name) == clean_name.lower()
        ).first()
        if duplicate_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lớp đã có học sinh tên '{clean_name}'. Vui lòng thêm họ, tên đệm hoặc ký hiệu phân biệt để tránh trùng tên!"
            )
        student.name = clean_name
    if student_in.school_class is not None:
        student.school_class = student_in.school_class.strip() if student_in.school_class else None
    if student_in.school_name is not None:
        student.school_name = student_in.school_name.strip() if student_in.school_name else None
    if student_in.parent_phone is not None:
        student.parent_phone = student_in.parent_phone.strip() if student_in.parent_phone else None
    if student_in.price_per_session is not None:
        student.price_per_session = float(student_in.price_per_session)
        
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    class_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa học sinh khỏi lớp học."""
    verify_classroom_ownership(class_id, current_user.id, db)
    
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.classroom_id == class_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học sinh này."
        )
        
    db.delete(student)
    db.commit()
    return None
