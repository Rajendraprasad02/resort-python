import asyncio
from typing import List, Optional, Dict, Any
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Configure a dedicated AI Transaction Logger
ai_logger = logging.getLogger("ai_interactions")
ai_logger.setLevel(logging.INFO)
if not ai_logger.handlers:
    fh = logging.FileHandler("logs/ai_interactions.log")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    ai_logger.addHandler(fh)

from groq import AsyncGroq
from app.core.config import settings

from app.db.session import AsyncSessionLocal
from app.models.ai_audit import AIAudit

class GroqCore:
    """Basic caller for Groq with rotation but no guardrails or complex audits yet."""
    def __init__(self):
        self._keys: List[str] = [k.strip() for k in settings.GROQ_API_KEYS.split(",") if k.strip()]
        self._current_key_index = 0
        self._clients: Dict[str, AsyncGroq] = {}

    def _get_client(self, api_key: str) -> AsyncGroq:
        if api_key not in self._clients:
            self._clients[api_key] = AsyncGroq(api_key=api_key)
        return self._clients[api_key]

    async def simple_call(self, model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        if not self._keys:
            raise ValueError("No GROQ_KEYS")
            
        for _ in range(len(self._keys)):
            current_key = self._keys[self._current_key_index]
            client = self._get_client(current_key)
            try:
                chat_completion = await client.chat.completions.create(
                    messages=messages,
                    model=model or settings.GROQ_MODEL_NAME,
                    temperature=0.1 # Low temp for guardrails
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                print(f"Core error: {e}")
                self._current_key_index = (self._current_key_index + 1) % len(self._keys)
                continue
        return None

groq_core = GroqCore()

class GroqService:
    def __init__(self):
        self.core = groq_core

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rate = 0.59 / 1_000_000 if "70b" in model.lower() else 0.05 / 1_000_000
        return (input_tokens + output_tokens) * rate

    async def _save_audit(self, model_name: str, messages: List[Dict[str, str]], response: str, usage: Any):
        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)
        cost = self._calculate_cost(model_name, input_tokens, output_tokens)
        
        # Build highly-built professional log entry
        prompt_blocks = ""
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            prompt_blocks += f"\n>>> [ROLE: {role}] <<<\n{content}\n"

        log_entry = (
            f"\n" + "="*80 + "\n"
            f" TRANSACTION ID: {datetime.now().strftime('%Y%m%d_%H%M%S_%f')}\n"
            f" MODEL: {model_name} | PROVIDER: Groq\n"
            f" INPUT PAYLOAD: {prompt_blocks}\n"
            f" {'-'*40}\n"
            f" FINAL RESPONSE:\n{response}\n"
            f" {'-'*40}\n"
            f" METRICS: In:{input_tokens} | Out:{output_tokens} | Total:{total_tokens}\n"
            f" ESTIMATED COST: ${cost:.6f}\n"
            f"================================================================================\n"
        )
        ai_logger.info(log_entry)
        
        async with AsyncSessionLocal() as db:
            audit = AIAudit(
                model_name=model_name,
                prompt=prompt_blocks[:1000], # Keep DB summary short
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
        Versatile LLM caller supporting either a message list or individual prompts.
        """
        model = model or settings.GROQ_MODEL_NAME
        
        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})

        last_message = messages[-1]["content"] if messages else ""

        # Core logic
        for _ in range(len(self.core._keys)):
            current_key = self.core._keys[self.core._current_key_index]
            client = self.core._get_client(current_key)
            
            try:
                chat_completion = await client.chat.completions.create(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                content = chat_completion.choices[0].message.content
                
                # Background audit
                asyncio.create_task(self._save_audit(
                    model_name=model,
                    messages=messages,
                    response=content,
                    usage=chat_completion.usage
                ))
                return {"role": "assistant", "content": content, "status": "success"}
            except Exception as e:
                print(f"Error with key rotation: {e}")
                self.core._current_key_index = (self.core._current_key_index + 1) % len(self.core._keys)
                continue
        return {"role": "assistant", "content": "Critical Error: Key Rotation Failed", "status": "error"}

groq_service = GroqService()
