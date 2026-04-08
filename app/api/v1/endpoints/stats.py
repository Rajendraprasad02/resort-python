from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.services import asset_service

router = APIRouter()

@router.get("/")
async def get_dashboard_stats(
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Return summarized metrics for the Dashboard cards (Total Revenue, Occupancy %, Active Guests).
    """
    return await asset_service.get_asset_stats(db)
