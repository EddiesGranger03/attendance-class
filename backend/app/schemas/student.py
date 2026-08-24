from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    school_class: Optional[str] = Field(None, max_length=100)
    school_name: Optional[str] = Field(None, max_length=255)
    parent_phone: Optional[str] = Field(None, max_length=50)
    price_per_session: float = Field(..., ge=0)


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    school_class: Optional[str] = Field(None, max_length=100)
    school_name: Optional[str] = Field(None, max_length=255)
    parent_phone: Optional[str] = Field(None, max_length=50)
    price_per_session: Optional[float] = Field(None, ge=0)


class StudentResponse(BaseModel):
    id: str
    classroom_id: str
    name: str
    school_class: Optional[str] = None
    school_name: Optional[str] = None
    parent_phone: Optional[str] = None
    price_per_session: float
    created_at: datetime

    class Config:
        from_attributes = True
