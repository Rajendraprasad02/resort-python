import logging
from typing import Any, Dict, List, Optional
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
from app.models.lead import Lead
import json
import base64
import re
import os

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

            # 3. IDENTIFY GUEST OR LEAD
            wa_logger.info(f"Step 3: Checking Databases for {db_from_number}...")
            
            # Check for existing Guest
            guest_stmt = select(Guest).where(Guest.phone == db_from_number)
            res = await db.execute(guest_stmt)
            guest = res.scalar_one_or_none()
            
            # Check for existing Lead
            lead_stmt = select(Lead).where(Lead.phone == db_from_number)
            res = await db.execute(lead_stmt)
            lead = res.scalar_one_or_none()

            # --- HANDOFF BYPASS ---
            # Check handoff from Lead first, then Guest (backwards compatibility)
            is_transferred = (lead and lead.transferred_to_agent) or (guest and getattr(guest, 'transferred_to_agent', False))
            
            if is_transferred:
                wa_logger.info(f"User {db_from_number} is assigned to an agent. Bypassing AI.")
                msg_val = "Submitted Registration Form" if "[FORM_SUBMITTED" in text_body else text_body
                new_convo = Conversation(
                    sender_number=db_from_number,
                    user_message=msg_val,
                    ai_response=None,
                    provider="live_agent",
                    guest_id=guest.id if guest else None,
                    lead_id=lead.id if lead else None
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
                # Prioritize updating Lead, but also update Guest if it exists
                target_obj = lead or guest
                if target_obj:
                    if hasattr(target_obj, 'whatsapp_template_status'):
                        target_obj.whatsapp_template_status = "SUBMITTED"
                    
                    try:
                        json_str = text_body.replace("[FORM_SUBMITTED: ", "")[:-1]
                        form_data = json.loads(json_str)
                        first_name = form_data.get("screen_0_First_0", "")
                        last_name = form_data.get("screen_0_Last_1", "")
                        target_obj.name = f"{first_name} {last_name}".strip() or "WhatsApp User"
                        target_obj.email = form_data.get("screen_0_Email_2", target_obj.email)
                        if hasattr(target_obj, 'address'):
                            target_obj.address = form_data.get("screen_0_Address_4", getattr(target_obj, 'address', None))
                        
                        await db.commit()
                        await db.refresh(target_obj)
                    except Exception as e:
                        await db.rollback()
                        wa_logger.error(f"Form parsing error: {e}")
                
                # Assign actual_user_query to the centralized prompt
                actual_user_query = prompts.WHATSAPP_FORM_SUBMITTED_INSTRUCTION
                # Override raw query to prevent PII Guardrail failure, but DB uses db_message_val
                text_body = "I have successfully submitted my registration form."

            elif guest is None and lead is None:
                # New user -> Create a Lead instead of a Guest
                lead = Lead(
                    phone=db_from_number, 
                    name="Unknown WhatsApp User", 
                    email=f"{from_number}@whatsapp.invalid",
                    source="WhatsApp",
                    whatsapp_template_status="NOT_SENT"
                )
                db.add(lead)
                await db.commit()
                await db.refresh(lead)
                needs_form = True
            elif lead and lead.whatsapp_template_status != "SUBMITTED":
                needs_form = True
            elif guest and lead is None:
                # Existing guest contact but no lead record (rare case)
                # We could create a lead or just proceed. Here we proceed.
                pass

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
            if "live agent" in ai_response.lower():
                if lead:
                    lead.transferred_to_agent = True
                if guest and hasattr(guest, 'transferred_to_agent'):
                    guest.transferred_to_agent = True
                await db.commit()
                wa_logger.info(f"Agent Handoff triggered for {from_number}")

            # 5. PERSIST THE CONVERSATION (Memory)
            new_convo = Conversation(
                sender_number=db_from_number,
                user_message=db_message_val,
                ai_response=ai_response,
                provider=provider,
                guest_id=guest.id if guest else None,
                lead_id=lead.id if lead else None
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
                if lead:
                    lead.whatsapp_template_status = "SENT"
                    await db.commit()
                elif guest and hasattr(guest, 'whatsapp_template_status'):
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
        
        # --- HANDLE STATUS UPDATES (Sent, Delivered, Read, Failed) ---
        statuses = value.get("statuses", [])
        if statuses:
            status = statuses[0]
            msg_id = status.get("id")
            status_val = status.get("status")
            recipient = status.get("recipient_id")
            
            if status_val == "failed":
                errors = status.get("errors", [])
                err_msg = errors[0].get("message") if errors else "Unknown logic error"
                wa_logger.error(f"[STATUS] {msg_id} to {recipient} FAILED: {err_msg}")
                term_alert(f"[STATUS] {msg_id} FAILED: {err_msg}")
            else:
                wa_logger.info(f"[STATUS] {msg_id} to {recipient} is {status_val}")
            
            return {"status": "success"}

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
    
    # Calculate window status
    from datetime import datetime, timedelta
    window_open = False
    time_left = None
    
    last_user_msg = next((c for c in reversed(convos) if c.user_message != "[Admin Outbound]"), None)
    if last_user_msg:
        time_diff = datetime.utcnow() - last_user_msg.created_at
        if time_diff < timedelta(hours=24):
            window_open = True
            time_left = str(timedelta(hours=24) - time_diff).split(".")[0]
            
    return {
        "sender_number": sender_number,
        "window_open": window_open,
        "time_left": time_left,
        "messages": convos
    }

from pydantic import BaseModel

class AdminMessageRequest(BaseModel):
    message: Optional[str] = None
    image_url: Optional[str] = None

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
    if not payload.message and not payload.image_url:
        raise HTTPException(status_code=400, detail="Either message or image_url must be provided")
        
    db_from_number = f"+{sender_number.strip()}" if not sender_number.startswith("+") else sender_number
    raw_number = sender_number.replace("+", "").strip()

    # Find the guest or lead to forcefully silence the AI agent
    guest_stmt = select(Guest).where(Guest.phone == db_from_number)
    res = await db.execute(guest_stmt)
    guest = res.scalar_one_or_none()
    
    lead_stmt = select(Lead).where(Lead.phone == db_from_number)
    res = await db.execute(lead_stmt)
    lead = res.scalar_one_or_none()

    # --- 24-HOUR WINDOW CHECK ---
    from datetime import datetime, timedelta
    
    # Logic: Window is open if the LAST message from the user was within 24 hours.
    # We ignore [Admin Outbound] and look for real incoming messages.
    window_stmt = select(Conversation).where(
        Conversation.sender_number == db_from_number,
        Conversation.user_message != "[Admin Outbound]"
    ).order_by(Conversation.created_at.desc()).limit(1)
    
    window_res = await db.execute(window_stmt)
    last_user_message = window_res.scalar_one_or_none()
    
    if last_user_message:
        # Check if it was more than 24 hours ago
        time_diff = datetime.utcnow() - last_user_message.created_at
        if time_diff > timedelta(hours=24):
            raise HTTPException(
                status_code=403, 
                detail=f"WhatsApp 24-hour window is CLOSED. Last customer message was {time_diff.hours if hasattr(time_diff, 'hours') else int(time_diff.total_seconds() // 3600)}h ago. Ask them to message you first."
            )
    else:
        # No history found, assume window is unknown or closed
        raise HTTPException(status_code=403, detail="No incoming message found from this user. You cannot initiate a conversation.")

    # Ask whatsapp_service to send it
    if payload.image_url:
        media_id = None
        # Handle Base64 Data URLs
        if payload.image_url.startswith("data:image"):
            try:
                # Extract base64 data and mime type
                # format: data:image/jpeg;base64,/9j/4AAQSk...
                match = re.search(r'data:(image/\w+);base64,(.*)', payload.image_url)
                if match:
                    mime_type = match.group(1)
                    ext = mime_type.split('/')[-1]
                    image_data = base64.b64decode(match.group(2))
                    
                    wa_logger.info(f"Uploading base64 image ({len(image_data)} bytes)...")
                    media_id = await whatsapp_service.upload_media(
                        media_content=image_data,
                        filename=f"admin_upload.{ext}",
                        mime_type=mime_type
                    )
                    wa_logger.info(f"Base64 Upload success, Media ID: {media_id}")
            except Exception as e:
                wa_logger.error(f"Base64 processing failed: {e}")
        
        # Handle Local Project URLs (localhost or current domain uploads)
        elif "/uploads/" in payload.image_url:
            try:
                # Extract the relative path. e.g. /uploads/property_images/abc.jpg
                # We expect the URL to contain '/uploads/'
                path_part = payload.image_url.split("/uploads/")[1]
                # Normalize slashes for Windows/Linux consistency
                path_part = path_part.replace("/", os.sep).replace("\\", os.sep)
                file_path = os.path.join("uploads", path_part)
                
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        image_data = f.read()
                    
                    mime_type = "image/jpeg" # Default
                    if file_path.lower().endswith(".png"): mime_type = "image/png"
                    elif file_path.lower().endswith(".webp"): mime_type = "image/webp"
                    
                    wa_logger.info(f"Uploading local file {file_path} ({len(image_data)} bytes)...")
                    media_id = await whatsapp_service.upload_media(
                        media_content=image_data,
                        filename=os.path.basename(file_path),
                        mime_type=mime_type
                    )
                    if media_id:
                        wa_logger.info(f"Local file upload success, Media ID: {media_id}")
                    else:
                        wa_logger.error("Local file upload failed (no media_id returned)")
                else:
                    wa_logger.error(f"Local file not found: {file_path}")
            except Exception as e:
                wa_logger.error(f"Local file processing failed: {e}")

        # Construct the path to log in DB (always relative path)
        log_url = payload.image_url
        if media_id and payload.image_url.startswith("data:image"):
             log_url = "Meta_Upload"
        elif "/uploads/" in payload.image_url:
             log_url = f"/uploads/{payload.image_url.split('/uploads/')[1]}"

        wa_res = await whatsapp_service.send_image_message(
            recipient_number=raw_number, 
            image_url=payload.image_url if not media_id else None, 
            media_id=media_id,
            caption=payload.message
        )
        msg_to_log = f"[Image: {log_url}] " + (payload.message or "")
    else:
        wa_res = await whatsapp_service.send_text_message(
            recipient_number=raw_number, 
            text=payload.message
        )
        msg_to_log = payload.message
    
    if wa_res.get("status") == "error":
        wa_logger.error(f"[ADMIN FAILED] Meta API Refused: {wa_res.get('message')}")
        raise HTTPException(status_code=500, detail=wa_res.get("message"))

    # Update status and log the message in one transaction
    if lead:
        lead.transferred_to_agent = True
        db.add(lead)
    
    if guest and hasattr(guest, 'transferred_to_agent'):
        guest.transferred_to_agent = True
        db.add(guest)

    new_convo = Conversation(
        sender_number=db_from_number,
        user_message="[Admin Outbound]",
        ai_response=msg_to_log,
        provider="live_agent",
        guest_id=guest.id if guest else None,
        lead_id=lead.id if lead else None
    )
    db.add(new_convo)
    await db.commit()
    
    wa_logger.info(f"[OUTGOING - ADMIN] TO: {raw_number} MSG: {payload.message}")
    
    return {"status": "success", "message": "Message dispatched successfully"}
