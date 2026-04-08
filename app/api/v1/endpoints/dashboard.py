from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services import dashboard_service
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/")
async def get_dashboard_summary(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_active_superuser)
) -> Any:
    metrics = await dashboard_service.get_dashboard_metrics(db)
    return metrics
