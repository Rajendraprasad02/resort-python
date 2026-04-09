from sqlalchemy import Column, Integer, String, Text, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Guest(Base):
    __tablename__ = "guest"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=True)
    
    # Source Tracking
    source = Column(String, default="Direct") # Direct, Online, WhatsApp, OTA, Corporate, Social, Others
    
    # ID Verification
    id_proof_type = Column(String) # Passport, National ID, Driver License, Others
    id_number = Column(String, nullable=False)
    id_proof_image_url = Column(String, nullable=True) # Local path/URL
    
    notes = Column(Text, nullable=True)
    
    # Loyalty & Stays (Computed usually, but can store last total)
    total_stays = Column(Integer, default=0)
    loyalty_tier = Column(String, default="Blue") # Blue, Silver, Gold, Platinum
    
    # Relationships
    reservations = relationship("Reservation", back_populates="guest")
