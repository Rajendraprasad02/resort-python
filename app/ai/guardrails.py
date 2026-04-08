from typing import Tuple, Optional, Any
from . import prompts
from app.core.config import settings

class AIGuardrails:
    async def validate_input(self, user_input: str, ai_service: Any, model: str) -> Tuple[bool, Optional[str]]:
        """Check input using the currently active LLM provider."""
        
        system_prompt = prompts.GUARDRAIL_SYSTEM
        user_prompt = prompts.GUARDRAIL_USER.format(user_input=user_input)
        
        # Standardized call using whichever service is passed
        response_obj = await ai_service.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=0.1
        )
        
        response = response_obj.get("content", "")
        
        if not response:
            return True, None
            
        if "UNSAFE" in response.upper():
            return False, response.strip()
            
        return True, None

    async def validate_output(self, assistant_response: str) -> Tuple[bool, Optional[str]]:
        """Optional: Verify output as well (can be slow so maybe skip for now or do asynchronously)."""
        return True, None

guardrail_service = AIGuardrails()
