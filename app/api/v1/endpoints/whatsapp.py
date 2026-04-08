import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.api import deps
from app.db.session import AsyncSessionLocal
from app.core.config import settings
from app.ai.agent_service import EliteHMAgent
from app.services.whatsapp_service import whatsapp_service
from app.models.conversation import Conversation
from app.models.guest import Guest
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# --- ENSURE GLOBAL LIBRARIES ARE FOUND ---
import sys
import site
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.append(user_site)

# --- DEDICATED WHATSAPP INTERACTION LOGGER ---
wa_logger = logging.getLogger("whatsapp_audit")
wa_logger.setLevel(logging.INFO)

# 1. File Handler (Persistent Log)
import os
os.makedirs("logs", exist_ok=True)
fh = logging.FileHandler("logs/whatsapp_interactions.log", encoding="utf-8")
fh.setFormatter(logging.Formatter('%(asctime)s - [WA] %(message)s'))
wa_logger.addHandler(fh)

# 2. Terminal Alert Function (The "Hammer" that always works)
# To bypass Uvicorn's aggressive reload filter, we must use the standard python `logging` directly on the root.
import sys
import logging
root_logger = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
root_logger.addHandler(ch)

def term_alert(msg):
    # This directly forces the message into the highest-level Python output stream
    root_logger.info(f"\n[WHATSAPP_EVENT] {msg}")

async def background_process_ai_response(from_number: str, text_body: str, media_id: str = None, message_type: str = "text"):
    """
    Handles heavy AI processing safely in the background to prevent WhatsApp timeouts.
    """
    db_from_number = f"+{from_number}" if not from_number.startswith("+") else from_number
    
    async with AsyncSessionLocal() as db:
        try:
            # 2. FETCH PERSISTENT CONVERSATION HISTORY
            wa_logger.info(f"Step 2: Retrieving context for {db_from_number}...")
            history = []
            # We fetch the last 4 interactions
            history_stmt = select(Conversation).where(
                Conversation.sender_number == db_from_number
            ).order_by(Conversation.created_at.desc()).limit(4)
            
            result = await db.execute(history_stmt)
            past_convos = result.scalars().all()
            wa_logger.info(f"History Found: {len(past_convos)} exchanges.")
            
            for convo in reversed(past_convos):
                history.append({"role": "user", "content": convo.user_message})
                if convo.ai_response:
                    history.append({"role": "assistant", "content": convo.ai_response})

            # 3. IDENTIFY GUEST
            wa_logger.info(f"Step 3: Checking Guest Database for {db_from_number}...")
            guest_stmt = select(Guest).where(Guest.phone == db_from_number)
            res = await db.execute(guest_stmt)
            guest = res.scalar_one_or_none()

            # --- HANDOFF BYPASS ---
            if guest and guest.transferred_to_agent:
                wa_logger.info(f"User {db_from_number} is assigned to an agent. Bypassing AI.")
                msg_val = "Submitted Registration Form" if "[FORM_SUBMITTED" in text_body else text_body
                new_convo = Conversation(
                    sender_number=db_from_number,
                    user_message=msg_val,
                    ai_response=None,
                    provider="live_agent",
                    guest_id=guest.id
                )
                db.add(new_convo)
                await db.commit()
                return

            needs_form = False
            actual_user_query = text_body
            db_message_val = text_body
            from app.ai import prompts
            
            # Handle Media Downloads in securely decoupled thread
            if media_id:
                import uuid
                import os
                media_bytes = await whatsapp_service.download_media(media_id)
                if media_bytes:
                    os.makedirs("uploads/whatsapp_media", exist_ok=True)
                    ext = "jpg" if message_type == "image" else "pdf" if message_type == "document" else "bin"
                    filename = f"uploads/whatsapp_media/{uuid.uuid4().hex}.{ext}"
                    with open(filename, "wb") as f:
                        f.write(media_bytes)
                    
                    db_message_val = f"[MEDIA RECEIVED: {filename}]"
                    text_body = f"I have just sent you a {message_type} file. Please acknowledge receipt."
                    wa_logger.info(f"Media successfully downloaded to {filename}")
                else:
                    db_message_val = f"[MEDIA ERROR: Could not download {media_id}]"
                    text_body = "I tried to send an image/file, but the system could not download it."

            # Check if this is a form submission message
            elif "[FORM_SUBMITTED" in text_body:
                if guest:
                    guest.whatsapp_template_status = "SUBMITTED"
                    # Parse JSON to update guest details natively
                    try:
                        json_str = text_body.replace("[FORM_SUBMITTED: ", "")[:-1]
                        form_data = json.loads(json_str)
                        first_name = form_data.get("screen_0_First_0", "")
                        last_name = form_data.get("screen_0_Last_1", "")
                        guest.name = f"{first_name} {last_name}".strip() or "WhatsApp User"
                        guest.email = form_data.get("screen_0_Email_2", guest.email)
                        guest.address = form_data.get("screen_0_Address_4", guest.address)
                        
                        await db.commit()
                        await db.refresh(guest) # CRITICAL: avoid greenlet_spawn error
                    except Exception as e:
                        await db.rollback()
                        wa_logger.error(f"Form parsing error: {e}")
                
                # Assign actual_user_query to the centralized prompt
                actual_user_query = prompts.WHATSAPP_FORM_SUBMITTED_INSTRUCTION
                # Override raw query to prevent PII Guardrail failure, but DB uses db_message_val
                text_body = "I have successfully submitted my registration form."

            elif guest is None:
                guest = Guest(
                    phone=db_from_number, 
                    name="Unknown WhatsApp User", 
                    email=f"{from_number}@whatsapp.invalid",
                    id_number="PENDING",
                    source="WhatsApp",
                    whatsapp_template_status="NOT_SENT"
                )
                db.add(guest)
                await db.commit()
                await db.refresh(guest)
                needs_form = True
            elif guest.whatsapp_template_status != "SUBMITTED":
                # If an admin or OTA created this guest, they already have a real name. We shouldn't send the form.
                if guest.name and guest.name != "Unknown WhatsApp User":
                    guest.whatsapp_template_status = "SUBMITTED"
                    await db.commit()
                else:
                    needs_form = True

            if needs_form:
                 # Wrap the text body with system instructions for the LLM
                 actual_user_query = prompts.WHATSAPP_FORM_INSTRUCTION.format(text_body=text_body)

            # 4. CALL THE ELITE CONCIERGE
            provider = settings.DEFAULT_AI_PROVIDER
            wa_logger.info(f"Step 4: Triggering LLM Brain ({provider})...")
            agent = EliteHMAgent(provider=provider)
            
            ai_response = await agent.process_request(
                db=db,
                user_query=actual_user_query,
                history=history,
                raw_user_query=text_body
            )
            wa_logger.info(f"LLM Response Generated: {len(ai_response)} chars.")

            # AUTO-HANDOFF DETECTION
            if "live agent" in ai_response.lower() and guest:
                guest.transferred_to_agent = True
                await db.commit()
                wa_logger.info(f"Agent Handoff triggered for {from_number}")

            # 5. PERSIST THE CONVERSATION (Memory)
            new_convo = Conversation(
                sender_number=db_from_number,
                user_message=db_message_val,
                ai_response=ai_response,
                provider=provider,
                guest_id=guest.id if guest else None
            )
            db.add(new_convo)
            await db.commit()

            # 6. BROADCAST TO WHATSAPP
            wa_logger.info(f"Step 6: Sending response to Meta for {from_number}...")
            wa_res = await whatsapp_service.send_text_message(recipient_number=from_number, text=ai_response)
            
            if needs_form:
                from app.services.whatsapp_templates import get_template_payload
                template_payload = get_template_payload(from_number, "basic_details")
                await whatsapp_service.send_template_message(from_number, template_payload)
                if guest:
                    guest.whatsapp_template_status = "SENT"
                    await db.commit()

            # --- LOG OUTGOING STATUS ---
            if wa_res.get("status") == "error":
                wa_logger.error(f"[FAILED] Meta API Refused: {wa_res.get('message')}")
                term_alert(f"[FAILED] Meta API Refused: {wa_res.get('message')}")
            else:
                wa_logger.info(f"[OUTGOING] TO: {from_number} RESPONSE: {ai_response}")
                term_alert(f"[OUTGOING] TO: {from_number} RESPONSE: {ai_response}")

        except Exception as e:
            wa_logger.error(f"Background Processing Fail: {str(e)}")
            term_alert(f"Background Processing Fail: {str(e)}")

@router.get("/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Standard Meta Webhook Verification.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp Webhook Verified Successfully.")
        return int(hub_challenge)
    
    logger.warning(f"Verification Failed. Expected {settings.WHATSAPP_VERIFY_TOKEN} but got {hub_verify_token}")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_whatsapp_message(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Elite WhatsApp Concierge: 
    - Decoupled Processing (BackgroundTasks) to avoid Meta timeouts.
    - Persistent Conversation Logging
    - Automated Response Handling
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Received an empty or non-JSON body on the WhatsApp webhook.")
        return {"status": "success", "detail": "Empty body"}

    try:
        # 1. PARSE INCOMING DATA
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "success"}

        message = messages[0]
        from_number = message.get("from")
        message_type = message.get("type")
        
        text_body = ""
        media_id = None
        
        if message_type == "text":
            text_body = message.get("text", {}).get("body")
        elif message_type in ["image", "document", "audio", "video"]:
            media_id = message.get(message_type, {}).get("id")
            text_body = f"[{message_type.upper()} RECEIVED]"
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "nfm_reply":
                response_json_str = interactive.get("nfm_reply", {}).get("response_json", "{}")
                text_body = f"[FORM_SUBMITTED: {response_json_str}]"
            elif interactive.get("type") == "button_reply":
                text_body = interactive.get("button_reply", {}).get("title", "")
        
        if not text_body and not media_id:
            return {"status": "success"}

        # --- LOG INCOMING MESSAGE ---
        wa_logger.info(f"[INCOMING] FROM: {from_number} MSG: {text_body}")
        term_alert(f"[INCOMING] FROM: {from_number} MSG: {text_body}")

        # Trigger Background Brain
        background_tasks.add_task(background_process_ai_response, from_number, text_body, media_id, message_type)

        # IMMEDIATELY return 200 OK to Meta to prevent retries
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Reception Error: {str(e)}")
        return {"status": "success"} # Still return success to prevent Meta retry loops


@router.get("/conversations")
async def get_all_conversations(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    phone_number: str = Query(None, description="Filter by sender number")
):
    """
    Retrieve all WhatsApp AI interactions.
    Optionally filter by sender_number.
    """
    try:
        stmt = select(Conversation).order_by(Conversation.created_at.desc())
        if phone_number:
            stmt = stmt.where(Conversation.sender_number == phone_number)
            
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail="Database Error")


@router.get("/conversations/{sender_number}")
async def get_conversation_by_sender(
    sender_number: str,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve WhatsApp conversation history for a specific sender_number.
    """
    # Just in case the frontend forgets to URL encode the '+' symbol
    if not sender_number.startswith("+"):
        # Removing any accidental blank space that might have replaced the + in unencoded URLs
        sender_number = f"+{sender_number.strip()}"
        
    stmt = select(Conversation).where(
        Conversation.sender_number == sender_number
    ).order_by(Conversation.created_at.asc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    convos = result.scalars().all()
    
    return convos

from pydantic import BaseModel

class AdminMessageRequest(BaseModel):
    message: str

@router.post("/conversations/{sender_number}/send")
async def send_admin_message(
    sender_number: str,
    payload: AdminMessageRequest,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Allows a human admin to send a message directly to the guest.
    Automatically flags the conversation as 'live_agent' and mutes AI responses.
    """
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    db_from_number = f"+{sender_number.strip()}" if not sender_number.startswith("+") else sender_number
    raw_number = sender_number.replace("+", "").strip()

    # Find the guest to forcefully silence the AI agent
    guest_stmt = select(Guest).where(Guest.phone == db_from_number)
    res = await db.execute(guest_stmt)
    guest = res.scalar_one_or_none()
    guest_id = guest.id if guest else None

    # Ask whatsapp_service to send it
    wa_res = await whatsapp_service.send_text_message(recipient_number=raw_number, text=payload.message)
    
    if wa_res.get("status") == "error":
        wa_logger.error(f"[ADMIN FAILED] Meta API Refused: {wa_res.get('message')}")
        raise HTTPException(status_code=500, detail=wa_res.get("message"))

    # Update guest status and log the message in one transaction
    if guest:
        guest.transferred_to_agent = True
        db.add(guest)

    new_convo = Conversation(
        sender_number=db_from_number,
        user_message="[Admin Outbound]",
        ai_response=payload.message,
        provider="live_agent",
        guest_id=guest_id
    )
    db.add(new_convo)
    await db.commit()
    
    wa_logger.info(f"[OUTGOING - ADMIN] TO: {raw_number} MSG: {payload.message}")
    
    return {"status": "success", "message": "Message dispatched successfully"}
