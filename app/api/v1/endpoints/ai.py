from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.agent_service import EliteHMAgent
from app.ai.groq_service import groq_service
from app.api import deps
from app.core.config import settings

router = APIRouter()

class AIRequest(BaseModel):
    preferences: str
    history: Optional[List[Dict[str, str]]] = None
    provider: Optional[str] = "gemini" # Default to Groq

@router.post("/recommend", response_model=dict)
async def get_ai_recommendation(
    request_in: AIRequest,
    db: AsyncSession = Depends(deps.get_db),
    # Auth is bypassed in development
    current_user: Any = Depends(deps.get_current_active_user)
) -> Any:
    """
    Enhanced AI Concierge: Now with Multi-Provider Support (Groq & Gemini).
    """
    # Use request provider if given, else use global default from .env
    provider = request_in.provider or settings.DEFAULT_AI_PROVIDER
    agent = EliteHMAgent(provider=provider)
    
    try:
        # Route the request with History context
        response = await agent.process_request(
            db, 
            request_in.preferences, 
            request_in.history
        )
        
        return {
            "user": current_user.full_name if hasattr(current_user, 'full_name') else "Guest",
            "recommendation": response
        }
    except ValueError as e:
        # This catches Guardrail violations
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected AI Error: {str(e)}")
