from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime

class GuestBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    address: Optional[str] = None
    source: Optional[str] = "Direct"
    id_proof_type: Optional[str] = None
    id_number: str
    notes: Optional[str] = None
    loyalty_tier: Optional[str] = "Blue"

class GuestCreate(GuestBase):
    pass

class GuestUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    id_proof_type: Optional[str] = None
    id_number: Optional[str] = None
    notes: Optional[str] = None
    loyalty_tier: Optional[str] = None
    id_proof_image_url: Optional[str] = None

class Guest(GuestBase):
    id: int
    total_stays: int
    id_proof_image_url: Optional[str] = None

    class Config:
        from_attributes = True
