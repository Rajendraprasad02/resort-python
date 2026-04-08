import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.groq_service import groq_service
from app.ai.gemini_service import gemini_service
from app.ai import prompts
from app.ai.guardrails import guardrail_service
from app.core.config import settings

logger = logging.getLogger(__name__)

class EliteHMAgent:
    """
    Elite HMS Multi-Layered AI Orchestrator.
    Now supports multiple providers (Groq, Gemini).
    """
    
    def __init__(self, provider: str = "groq"):
        self.provider = provider.lower()
        if self.provider == "gemini":
            self.ai = gemini_service
            self.model = settings.GEMINI_MODEL_NAME
        else:
            self.ai = groq_service
            self.model = settings.GROQ_MODEL_NAME

    async def process_request(self, db: AsyncSession, user_query: str, history: List[Dict[str, str]] = None, raw_user_query: str = None) -> str:
        """
        Main entry point with Contextual Memory & DYNAMIC GUARDRAILS.
        """
        history = history or []
        query_to_validate = raw_user_query if raw_user_query else user_query
        logger.info(f"Processing Request with Provider [{self.provider}]: '{query_to_validate}'")

        # --- STEP 0: DYNAMIC GUARDRAIL (Uses the active provider) ---
        is_safe, reason = await guardrail_service.validate_input(
            query_to_validate, 
            ai_service=self.ai, 
            model=self.model
        )
        if not is_safe:
            return f"I'm sorry, but I cannot assist with that request. Reason: {reason}"

        # 1. STEP 1: ROUTING (Decision Prompt)
        router_prompt = f"Previous Conversation:\n{json.dumps(history)}\n\nCurrent User Query: {user_query}"
        
        router_response = await self.ai.call_llm(
            system_prompt=prompts.AGENT_ROUTER_SYSTEM,
            user_prompt=router_prompt,
            model=self.model,
            response_format={"type": "json_object"}
        )
        
        try:
            intent = json.loads(router_response.get("content", "{}")).get("intent_key", "GENERAL_CHAT")
        except Exception:
            intent = "GENERAL_CHAT"

        logger.info(f"Contextual Intent Detected: {intent}")

        # 2. STEP 2: PATHWAY EXECUTION
        if intent == "CHECK_AVAILABILITY":
            return await self._handle_availability_check(db, user_query, history)
        elif intent == "DATABASE_QUERY":
            return await self._handle_database_query(db, user_query, history)
        else:
            return await self._handle_general_chat(user_query, history)

    async def _handle_database_query(self, db: AsyncSession, user_query: str, history: List[Dict[str, str]]) -> str:
        """
        Context-Injection LLM: Passes entire inventory context to the LLM.
        """
        # Fetch active inventory from the database for full transparency and zero-hallucination
        try:
            inventory_res = await db.execute(text(
                "SELECT id, name, type, location_name, landmark, view, base_price, "
                "(COALESCE(max_adults,0) + COALESCE(max_children,0)) as capacity "
                "FROM property_asset WHERE status = 'Available'"
            ))
            rows = inventory_res.mappings().all()
            
            if not rows:
                data_summary = "NO_PROPERTIES_AVAILABLE"
            else:
                data_summary = str([dict(row) for row in rows])
                
        except Exception as e:
            logger.error(f"Database Fetch Error: {str(e)}")
            data_summary = "DATABASE_ERROR_OCCURRED"

        # Contextual Humanize
        # We pass history, user query and all property data to the humanizer
        humanizer_input = f"CONVERSATION_HISTORY: {json.dumps(history)}\n\nAVAILABLE_PROPERTY_DATA: {data_summary}\n\nCURRENT_USER_QUERY: {user_query}"
        
        final_response = await self.ai.call_llm(
            system_prompt=prompts.FINAL_CONCIERGE_SYSTEM,
            user_prompt=humanizer_input,
            model=self.model
        )
        
        return final_response.get("content", "I encountered an error. Please try again.")

    async def _handle_availability_check(self, db: AsyncSession, user_query: str, history: List[Dict[str, str]]) -> str:
        """
        Generates SQL to check reservations for specific properties.
        """
        try:
            # Fetch active inventory so LLM can map names to IDs
            inventory_res = await db.execute(text("SELECT id, name FROM property_asset WHERE status = 'Available'"))
            rows = inventory_res.mappings().all()
            inventory_str = str([dict(row) for row in rows])

            current_date = datetime.now().strftime("%Y-%m-%d (%A)")
            sql_input = f"CURRENT_DATE: {current_date}\nCONVERSATION_HISTORY: {json.dumps(history)}\nQUERY: {user_query}\nMATCHING_PROPERTIES: {inventory_str}"

            sql_response = await self.ai.call_llm(
                system_prompt=prompts.RESERVATION_SQL_SYSTEM,
                user_prompt=sql_input,
                model=self.model
            )
            
            generated_sql = sql_response.get("content", "").strip()
            logger.info(f"Availability Generated SQL: {generated_sql}")
            
            if not generated_sql.upper().startswith("SELECT"):
                data_summary = "SQL_GENERATION_FAILED. Could not determine the query to check availability."
            else:
                result = await db.execute(text(generated_sql))
                future_reservations = result.mappings().all()
                if future_reservations:
                    data_summary = f"FUTURE_RESERVATIONS_FOR_PROPERTY: {str([dict(r) for r in future_reservations])}. **You must check if these overlap with the guest's dates.**"
                else:
                    data_summary = "NO_FUTURE_RESERVATIONS. The property is completely available."
        except Exception as e:
            logger.error(f"Availability SQL Execution Error: {str(e)}")
            data_summary = "DATABASE_ERROR_OCCURRED"

        # Pass it to Humanizer
        humanizer_input = f"CONVERSATION_HISTORY: {json.dumps(history)}\n\nAVAILABILITY_DATA: {data_summary}\n\nCURRENT_USER_QUERY: {user_query}"
        
        final_response = await self.ai.call_llm(
            system_prompt=prompts.FINAL_CONCIERGE_SYSTEM,
            user_prompt=humanizer_input,
            model=self.model
        )
        return final_response.get("content", "I encountered an error. Please try again.")

    async def _handle_general_chat(self, user_query: str, history: List[Dict[str, str]]) -> str:
        """
        Conversational response with history.
        """
        chat_input = f"HISTORY: {json.dumps(history)}\nUSER: {user_query}"
        response = await self.ai.call_llm(
            system_prompt=prompts.GENERAL_CHAT_SYSTEM,
            user_prompt=chat_input,
            model=self.model
        )
        return response.get("content", "Greetings! How can I help you?")
