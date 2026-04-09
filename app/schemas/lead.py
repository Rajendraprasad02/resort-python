from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

class LeadBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    source: Optional[str] = "WhatsApp"
    whatsapp_template_status: Optional[str] = "NOT_SENT"
    transferred_to_agent: Optional[bool] = False

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp_template_status: Optional[str] = None
    transferred_to_agent: Optional[bool] = None
    is_converted: Optional[bool] = None

class Lead(LeadBase):
    id: int
    is_converted: bool
    guest_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
