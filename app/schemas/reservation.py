from typing import Optional
from pydantic import BaseModel
from datetime import datetime, date

class ReservationBase(BaseModel):
    asset_id: int
    guest_id: Optional[int] = None
    guest_name: Optional[str] = None
    check_in: date
    check_out: date
    status: Optional[str] = "Pending"
    total_price: float

class ReservationCreate(ReservationBase):
    pass

class ReservationUpdate(BaseModel):
    asset_id: Optional[int] = None
    guest_id: Optional[int] = None
    guest_name: Optional[str] = None
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    status: Optional[str] = None
    total_price: Optional[float] = None

class Reservation(ReservationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
