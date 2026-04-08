import asyncio
import logging
from typing import List, Optional, Dict, Any

# --- ENSURE GLOBAL LIBRARIES ARE FOUND ---
import sys
import site
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.append(user_site)

import google.genai as genai
from google.genai import types
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.ai_audit import AIAudit

logger = logging.getLogger(__name__)
ai_logger = logging.getLogger("ai_interactions")

class GeminiService:
    def __init__(self):
        # The NEW Unified Gemini SDK Client
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.GEMINI_MODEL_NAME or "gemini-1.5-flash"

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        # Gemini 1.5 Flash Pricing (Standard)
        # Input: $0.075 / 1M tokens, Output: $0.30 / 1M tokens
        in_rate = 0.075 / 1_000_000
        out_rate = 0.30 / 1_000_000
        return (input_tokens * in_rate) + (output_tokens * out_rate)

    async def _save_audit(self, model_name: str, prompt: str, response: str, input_tokens: int, output_tokens: int):
        input_tokens = input_tokens or 0
        output_tokens = output_tokens or 0
        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(model_name, input_tokens, output_tokens)
        
        # Log to file
        log_entry = (
            f"\n--- GEMINI TRANSACTON (NEW SDK) ---\n"
            f"MODEL: {model_name}\n"
            f"PROMPT: {prompt}\n"
            f"RESPONSE: {response}\n"
            f"TOKENS: In:{input_tokens} Out:{output_tokens} Total:{total_tokens}\n"
            f"ESTIMATED COST: ${cost:.6f}\n"
            f"----------------------\n"
        )
        ai_logger.info(log_entry)
        
        async with AsyncSessionLocal() as db:
            audit = AIAudit(
                model_name=f"gemini/{model_name}",
                prompt=prompt,
                response=response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost
            )
            db.add(audit)
            await db.commit()

    async def call_llm(
        self, 
        model: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None, 
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        temperature: float = 0.7, 
        max_tokens: int = 1000,
        **kwargs: Any
    ) -> Dict[str, str]:
        """
        Gemini Caller using the BRAND NEW google-genai SDK.
        """
        target_model = model or self.model_id
        
        # 1. Format for NEW Gemini SDK
        system_instr = ""
        contents = [] # This is for simple generate_content
        
        if messages:
            # We convert Groq-style messages to Gemini-style contents
            for msg in messages:
                if msg["role"] == "system":
                    system_instr += msg["content"] + "\n"
                else:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        else:
            if system_prompt:
                system_instr = system_prompt
            if user_prompt:
                contents.append(types.Content(role="user", parts=[types.Part(text=user_prompt)]))

        last_prompt = user_prompt or (messages[-1]["content"] if messages else "")

        # --- DYNAMIC MAPPING FOR NEW SDK ---
        # If the orchestrator asks for JSON (for the router), we translate it for Gemini
        mime_type = None
        if kwargs.get("response_format", {}).get("type") == "json_object":
            mime_type = "application/json"
            # We must remove the field Gemini doesn't like from the kwargs
            kwargs.pop("response_format", None)

        try:
            # The new SDK is much cleaner
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=target_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instr if system_instr else None,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    response_mime_type=mime_type,
                    **kwargs
                )
            )
            
            content = response.text
            
            # Audit handling
            usage = response.usage_metadata
            if usage:
                asyncio.create_task(self._save_audit(
                    model_name=target_model,
                    prompt=last_prompt,
                    response=content,
                    input_tokens=usage.prompt_token_count,
                    output_tokens=usage.candidates_token_count
                ))
            
            return {"role": "assistant", "content": content, "status": "success"}

        except Exception as e:
            logger.error(f"Gemini NEW SDK Error: {str(e)}")
            return {"role": "assistant", "content": f"Gemini Error: {str(e)}", "status": "error"}

gemini_service = GeminiService()
