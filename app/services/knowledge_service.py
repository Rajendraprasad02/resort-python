from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.knowledge import KnowledgeArticle
from app.schemas.knowledge import KnowledgeArticleCreate

async def get_articles(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[KnowledgeArticle]:
    result = await db.execute(select(KnowledgeArticle).offset(skip).limit(limit))
    return result.scalars().all()

async def get_article(db: AsyncSession, article_id: int) -> Optional[KnowledgeArticle]:
    result = await db.execute(select(KnowledgeArticle).filter(KnowledgeArticle.id == article_id))
    return result.scalars().first()

async def create_article(db: AsyncSession, article_in: KnowledgeArticleCreate) -> KnowledgeArticle:
    db_obj = KnowledgeArticle(**article_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
