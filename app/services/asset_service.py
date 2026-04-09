from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.asset import PropertyAsset, AssetImage
from app.schemas.asset import PropertyAssetCreate, PropertyAssetUpdate, PropertyAssetStatusUpdate
from app.utils.file_handler import save_base64_image

async def create_asset(db: AsyncSession, asset_in: PropertyAssetCreate) -> PropertyAsset:
    asset_data = asset_in.model_dump()
    images_data = asset_data.pop("images", [])
    
    db_obj = PropertyAsset(**asset_data)
    
    # Map images directly to the relationship and save files if they are base64
    db_obj.images = []
    for img in images_data:
        # Save base64 data to disk and get the new URL
        img["url"] = save_base64_image(img.get("url"), subfolder="property_images")
        db_obj.images.append(AssetImage(**img))
        
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_assets(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100, 
    asset_type: Optional[str] = None,
    status: Optional[str] = None,
    name: Optional[str] = None,
    asset_id: Optional[int] = None
) -> List[PropertyAsset]:
    query = select(PropertyAsset)
    if asset_type:
        query = query.filter(PropertyAsset.type == asset_type)
    if status:
        query = query.filter(PropertyAsset.status == status)
    if name:
        query = query.filter(PropertyAsset.name.ilike(f"%{name}%"))
    if asset_id:
        query = query.filter(PropertyAsset.id == asset_id)
    
    # Only return non-deleted assets
    query = query.filter(PropertyAsset.is_deleted == False)
        
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

async def get_asset(db: AsyncSession, asset_id: int) -> Optional[PropertyAsset]:
    result = await db.execute(
        select(PropertyAsset).filter(PropertyAsset.id == asset_id, PropertyAsset.is_deleted == False)
    )
    return result.scalars().first()

async def update_asset(db: AsyncSession, asset_id: int, asset_in: PropertyAssetUpdate) -> Optional[PropertyAsset]:
    asset = await get_asset(db, asset_id)
    if not asset:
        return None
        
    update_data = asset_in.model_dump(exclude_unset=True)
    images_data = update_data.pop("images", None)
    
    for field, value in update_data.items():
        setattr(asset, field, value)
    
    if images_data is not None:
        # Using cascade='all, delete-orphan' to replace images automatically
        processed_images = []
        for img in images_data:
            img["url"] = save_base64_image(img.get("url"), subfolder="property_images")
            processed_images.append(AssetImage(**img, asset_id=asset_id))
        asset.images = processed_images
            
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset

async def update_asset_status(db: AsyncSession, asset_id: int, status_in: PropertyAssetStatusUpdate) -> Optional[PropertyAsset]:
    asset = await get_asset(db, asset_id)
    if not asset:
        return None
        
    update_data = status_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
        
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset

async def delete_asset(db: AsyncSession, asset_id: int) -> bool:
    asset = await get_asset(db, asset_id)
    if not asset:
        return False
    
    # Soft delete
    asset.is_deleted = True
    db.add(asset)
    await db.commit()
    return True

async def clone_asset(db: AsyncSession, asset_id: int) -> Optional[PropertyAsset]:
    """
    Creates a duplicate of an existing asset including its images.
    """
    # 1. Fetch the original asset
    original = await get_asset(db, asset_id)
    if not original:
        return None
    
    # 2. Extract data excluding system fields
    exclude_fields = {"id", "created_at", "updated_at", "is_deleted"}
    asset_data = {
        column.name: getattr(original, column.name)
        for column in original.__table__.columns
        if column.name not in exclude_fields
    }
    
    # 3. Modify name to indicate it's a clone
    asset_data["name"] = f"{asset_data['name']} (Copy)"
    
    # 4. Create new asset object
    cloned_asset = PropertyAsset(**asset_data)
    
    # 5. Clone images deep copy
    cloned_asset.images = [
        AssetImage(
            url=img.url,
            description=img.description,
            is_cover=img.is_cover
        ) for img in original.images
    ]
    
    db.add(cloned_asset)
    await db.commit()
    await db.refresh(cloned_asset)
    return cloned_asset

async def get_asset_stats(db: AsyncSession) -> dict:
    total_assets = (await db.execute(select(func.count(PropertyAsset.id)).filter(PropertyAsset.is_deleted == False))).scalar() or 0
    occupied_assets = (await db.execute(select(func.count(PropertyAsset.id)).filter(PropertyAsset.status == "Occupied", PropertyAsset.is_deleted == False))).scalar() or 0
    available_assets = (await db.execute(select(func.count(PropertyAsset.id)).filter(PropertyAsset.status == "Available", PropertyAsset.is_deleted == False))).scalar() or 0
    
    total_revenue = (await db.execute(select(func.sum(PropertyAsset.base_price).filter(PropertyAsset.status == "Occupied", PropertyAsset.is_deleted == False)))).scalar() or 0.0
    
    occupancy_pct = (occupied_assets / total_assets * 100) if total_assets > 0 else 0.0
    
    return {
        "total_revenue": total_revenue,
        "occupancy_percentage": occupancy_pct,
        "active_guests": occupied_assets, # Assuming 1 guest/occupancy for now or just using as dummy
        "total_assets": total_assets,
        "available_assets": available_assets
    }
