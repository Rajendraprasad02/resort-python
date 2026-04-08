from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.asset import PropertyAsset, PropertyAssetCreate, PropertyAssetUpdate, PropertyAssetStatusUpdate
from app.services import asset_service

router = APIRouter()

@router.post("/", response_model=PropertyAsset, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_in: PropertyAssetCreate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Save a new property asset (Room, Villa, or Property).
    """
    return await asset_service.create_asset(db, asset_in=asset_in)

@router.get("/", response_model=List[PropertyAsset])
async def read_assets(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    asset_type: Optional[str] = Query(None, description="Filter by asset type (room, villa, property)"),
    status: Optional[str] = Query(None, description="Filter by current status"),
    name: Optional[str] = Query(None, description="Search by asset name"),
    asset_id: Optional[int] = Query(None, description="Search by specific ID")
) -> Any:
    """
    Fetch all assets with optional filtering and searching.
    """
    return await asset_service.get_assets(
        db, 
        skip=skip, 
        limit=limit, 
        asset_type=asset_type, 
        status=status,
        name=name,
        asset_id=asset_id
    )

@router.get("/{asset_id}", response_model=PropertyAsset)
async def read_asset(
    asset_id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Fetch detailed information for a specific asset.
    """
    asset = await asset_service.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Property Asset not found")
    return asset

@router.patch("/{asset_id}", response_model=PropertyAsset)
async def update_asset_details(
    asset_id: int,
    asset_in: PropertyAssetUpdate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Update general asset details (e.g., price, configuration).
    """
    asset = await asset_service.update_asset(db, asset_id, asset_in)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.patch("/{asset_id}/status", response_model=PropertyAsset)
async def update_asset_operational_status(
    asset_id: int,
    status_in: PropertyAssetStatusUpdate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Optimized endpoint for updating Operational Status or Cleaning Status (daily housekeeping).
    """
    asset = await asset_service.update_asset_status(db, asset_id, status_in)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Archive or remove an asset from the inventory.
    """
    success = await asset_service.delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted successfully"}
