from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base

class Reservation(Base):
    __tablename__ = "reservation"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("property_asset.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(Integer, ForeignKey("guest.id", ondelete="SET NULL"), nullable=True) # Link to Guests
    user_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True) # Staff who created it
    
    guest_name = Column(String, nullable=True) # Optional back-up or used for quick creation
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    
    # Operational Flags: Confirmed, Paid, Advanced Paid, Need to Pay, Pending, Checked-In, Cancelled
    status = Column(String, default="Pending") 
    
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship Links
    asset = relationship("PropertyAsset", backref="reservations")
    guest = relationship("Guest", back_populates="reservations")
    user = relationship("User", back_populates="reservations")
