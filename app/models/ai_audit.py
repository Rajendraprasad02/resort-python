from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from app.db.base_class import Base

class AIAudit(Base):
    __tablename__ = "ai_audit"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    prompt = Column(Text)
    response = Column(Text)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
