from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.knowledge import KnowledgeArticleCreate, KnowledgeArticle
from app.services import knowledge_service
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[KnowledgeArticle])
async def read_articles(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    return await knowledge_service.get_articles(db, skip=skip, limit=limit)

@router.post("/", response_model=KnowledgeArticle)
async def create_article(
    article_in: KnowledgeArticleCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_active_superuser)
) -> Any:
    return await knowledge_service.create_article(db, article_in=article_in)
