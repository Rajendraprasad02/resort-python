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

    async def send_image_message(self, recipient_number: str, image_url: Optional[str] = None, media_id: Optional[str] = None, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an image message to the guest on WhatsApp. 
        Supports either a public 'image_url' (link) or a Meta 'media_id'.
        """
        if not self.phone_id or not self.token:
            return {"status": "error", "message": "Config missing"}

        image_payload = {}
        if media_id:
            image_payload = {"id": media_id}
        elif image_url:
            image_payload = {"link": image_url}
        else:
            return {"status": "error", "message": "Neither image_url nor media_id provided"}

        if caption:
            image_payload["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "image",
            "image": image_payload
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Use root logger for audit instead of circular import
        audit_logger = logging.getLogger("whatsapp_audit")
        audit_logger.info(f"[META_IMAGE_PAYLOAD]: {payload}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=headers)
                # --- LOG RAW RESPONSE ---
                audit_logger.info(f"[META_IMAGE_RESPONSE]: {response.text}")
                response.raise_for_status()
                return response.json()
            except Exception as e:
                audit_logger.error(f"[META_IMAGE_ERROR]: {str(e)}")
                return {"status": "error", "message": str(e)}

    async def upload_media(self, media_content: bytes, filename: str, mime_type: str) -> Optional[str]:
        """
        Uploads a media file (like an image/pdf) to Meta's servers.
        Returns the media_id if successful.
        """
        if not self.phone_id or not self.token:
            return None

        # --- IMPORTANT: FOR MEDIA UPLOAD, THE BASE URL IS DIFFERENT ---
        # It's /<phone_id>/media, not /<phone_id>/messages
        upload_url = f"https://graph.facebook.com/{self.version}/{self.phone_id}/media"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Meta expects 'file' part, and 'messaging_product' as data
        # We also pass 'type' as per some documentation requirements
        files = {'file': (filename, media_content, mime_type)}
        data = {
            'messaging_product': 'whatsapp',
            'type': mime_type
        }

        # Use root logger for audit instead of circular import
        audit_logger = logging.getLogger("whatsapp_audit")
        audit_logger.info(f"[META_MEDIA_UPLOAD_START]: File={filename}, Mime={mime_type}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(upload_url, headers=headers, files=files, data=data)
                audit_logger.info(f"[META_MEDIA_UPLOAD_RESPONSE]: {response.text}")
                response.raise_for_status()
                return response.json().get("id")
            except Exception as e:
                audit_logger.error(f"WhatsApp Media upload failed: {str(e)}")
                return None

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
