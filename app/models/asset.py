from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base

class PropertyAsset(Base):
    __tablename__ = "property_asset"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)  # room, villa, property
    status = Column(String, index=True, default="Available")  # Available, Occupied, Maintenance, Reserved
    cleaning_status = Column(String, index=True, default="Ready")  # Ready, Checked, Needs Cleaning
    
    # Pricing & Capacity
    base_price = Column(Float, default=0.0)
    max_adults = Column(Integer, default=2)
    max_children = Column(Integer, default=0)
    extra_beds_limit = Column(Integer, default=0)
    breakfast_included = Column(Boolean, default=False)
    
    # Logistics
    bedrooms = Column(Integer, default=1)
    bed_config = Column(String)  # King, Twin, etc.
    floor = Column(String)
    view = Column(String)  # Ocean, Garden, etc.
    pool_type = Column(String)  # Private, Common, None
    
    # Geographical Metadata
    location_name = Column(String, index=True)  # e.g., "North Wing"
    landmark = Column(String)  # e.g., "Near Zen Garden"
    map_link = Column(String)  # Google Maps URL
    description = Column(String) # Detailed narrative
    
    # Relationship for Multiple Images
    images = relationship("AssetImage", back_populates="asset", cascade="all, delete-orphan", lazy="selectin")
    
    # Timestamps & Soft Delete
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AssetImage(Base):
    __tablename__ = "asset_image"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("property_asset.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_cover = Column(Boolean, default=False)
    
    asset = relationship("PropertyAsset", back_populates="images")
