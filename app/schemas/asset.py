from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class AssetImageBase(BaseModel):
    url: str
    description: Optional[str] = None
    is_cover: bool = False

class AssetImage(AssetImageBase):
    id: int
    class Config:
        from_attributes = True

class PropertyAssetBase(BaseModel):
    name: str
    type: str = Field(..., pattern="^(room|villa|property)$")
    status: Optional[str] = "Available"
    cleaning_status: Optional[str] = "Ready"
    
    base_price: float = 0.0
    max_adults: int = 2
    max_children: int = 0
    extra_beds_limit: int = 0
    breakfast_included: bool = False
    
    bedrooms: int = 1
    bed_config: Optional[str] = None
    floor: Optional[str] = None
    view: Optional[str] = None
    pool_type: Optional[str] = None
    
    # Geographical metadata
    location_name: Optional[str] = None
    landmark: Optional[str] = None
    map_link: Optional[str] = None
    description: Optional[str] = None
    
    images: Optional[List[AssetImageBase]] = Field(default=[], description="List of images with descriptions and cover status")

class PropertyAssetCreate(PropertyAssetBase):
    pass

class PropertyAssetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    cleaning_status: Optional[str] = None
    base_price: Optional[float] = None
    max_adults: Optional[int] = None
    max_children: Optional[int] = None
    extra_beds_limit: Optional[int] = None
    breakfast_included: Optional[bool] = None
    bedrooms: Optional[int] = None
    bed_config: Optional[str] = None
    floor: Optional[str] = None
    view: Optional[str] = None
    pool_type: Optional[str] = None
    location_name: Optional[str] = None
    landmark: Optional[str] = None
    map_link: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[AssetImageBase]] = None

class PropertyAssetStatusUpdate(BaseModel):
    status: Optional[str] = None
    cleaning_status: Optional[str] = None

class PropertyAsset(PropertyAssetBase):
    id: int
    images: List[AssetImage] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AssetStats(BaseModel):
    total_assets: int
    active_assets: int
    occupancy_percentage: float
    total_potential_revenue: float
