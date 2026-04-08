import httpx
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.token = settings.WHATSAPP_ACCESS_TOKEN
        self.version = settings.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.version}/{self.phone_id}/messages"

    async def send_text_message(self, recipient_number: str, text: str) -> Dict[str, Any]:
        """
        Sends a standard text message back to the guest on WhatsApp.
        """
        if not self.phone_id or not self.token:
            logger.error("WhatsApp Configuration missing: Phone ID or Token is empty.")
            return {"status": "error", "message": "Config missing"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # --- AUDIT LOG FOR META HANDSHAKE ---
        print(f"\n[META_PAYLOAD]: JSON={payload} URL={self.base_url}", flush=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=headers)
                # --- LOG RAW RESPONSE FROM FACEBOOK ---
                print(f"\n[META_RESPONSE]: {response.text}", flush=True)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"\n[META_ERROR]: {e.response.text}", flush=True)
                return {"status": "error", "message": f"HTTP_{e.response.status_code}: {e.response.text}"}
            except Exception as e:
                print(f"\n[META_CONNECTION_FAILED]: {str(e)}", flush=True)
                return {"status": "error", "message": str(e)}

    async def send_template_message(self, recipient_number: str, template_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a WhatsApp template message (e.g. for Flow/Forms).
        """
        if not self.phone_id or not self.token:
            logger.error("WhatsApp Configuration missing: Phone ID or Token is empty.")
            return {"status": "error", "message": "Config missing"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        print(f"\n[META_TEMPLATE_PAYLOAD]: JSON={template_payload} URL={self.base_url}", flush=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=template_payload, headers=headers)
                print(f"\n[META_TEMPLATE_RESPONSE]: {response.text}", flush=True)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"\n[META_TEMPLATE_ERROR]: {e.response.text}", flush=True)
                return {"status": "error", "message": f"HTTP_{e.response.status_code}: {e.response.text}"}
            except Exception as e:
                print(f"\n[META_TEMPLATE_FAILED]: {str(e)}", flush=True)
                return {"status": "error", "message": str(e)}

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Downloads a media file from WhatsApp by first fetching the secure URL,
        then downloading the encrypted binary payload using the Bearer Token.
        """
        if not self.token:
            return None
            
        url_endpoint = f"https://graph.facebook.com/{self.version}/{media_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. Fetch the media temporary URL
                res = await client.get(url_endpoint, headers=headers)
                res.raise_for_status()
                media_url = res.json().get("url")
                
                if not media_url:
                    return None
                
                # 2. Download the binary payload using the URL 
                # (You MUST pass the Bearer token again to decrypt the edge URL)
                media_res = await client.get(media_url, headers=headers)
                media_res.raise_for_status()
                return media_res.content
            except Exception as e:
                logger.error(f"WhatsApp Media download failed for {media_id}: {str(e)}")
                return None

whatsapp_service = WhatsAppService()
