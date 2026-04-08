from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from .groq_service import groq_service
from app.core.config import settings

class AIPrompt(BaseModel):
    model_name: str = Field(default_factory=lambda: settings.GROQ_MODEL_NAME)
    system_prompt: str = "You are a helpful assistant for a Resort Booking Application."
    user_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stream: bool = False
    stop: Optional[List[str]] = None

    async def execute(self) -> Optional[str]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
        ]
        
        response = await groq_service.call_llm(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            stream=self.stream,
            stop=self.stop
        )
        return response.get("content")

# Example usage for different resort-related tasks
class ResortDescriber(AIPrompt):
    system_prompt: str = "You are a professional luxury travel writer. Describe resorts in a vivid, high-end tone."
    user_prompt: str = "" # Provide specific resort facts here
