from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class KnowledgeArticleBase(BaseModel):
    title: str
    content: str
    category: Optional[str] = None

class KnowledgeArticleCreate(KnowledgeArticleBase):
    pass

class KnowledgeArticleUpdate(KnowledgeArticleBase):
    pass

class KnowledgeArticle(KnowledgeArticleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
