from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Lead(Base):
    __tablename__ = "lead"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Unknown WhatsApp User")
    phone = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)
    source = Column(String, default="WhatsApp")
    
    # WhatsApp specific status (Moved from Guest for cleaner separation)
    whatsapp_template_status = Column(String, default="NOT_SENT") # NOT_SENT, SENT, SUBMITTED
    transferred_to_agent = Column(Boolean, default=False)
    
    # Management
    is_converted = Column(Boolean, default=False)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    guest = relationship("Guest", backref="lead_source")
    conversations = relationship("Conversation", back_populates="lead")
