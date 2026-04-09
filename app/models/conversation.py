from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)
    sender_number = Column(String, index=True, nullable=False) # The Guest's WhatsApp Number
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=True)
    provider = Column(String, nullable=True) # groq or gemini
    created_at = Column(DateTime, default=datetime.utcnow)

    # Optional: Links to Lead or Guest
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("lead.id"), nullable=True)

    guest = relationship("Guest", backref="conversations")
    lead = relationship("Lead", back_populates="conversations")
