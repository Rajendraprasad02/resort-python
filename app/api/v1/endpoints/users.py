from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.user import UserCreate, User
from app.services import user_service
from app.models.user import User as UserModel

router = APIRouter()

@router.post("/", response_model=User)
async def create_user_endpoint(
    user_in: UserCreate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    user = await user_service.create_user(db, user_in=user_in)
    return user

@router.get("/me", response_model=User)
async def read_user_me(
    current_user: UserModel = Depends(deps.get_current_active_user)
) -> Any:
    return current_user
