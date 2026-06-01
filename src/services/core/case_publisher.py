import asyncio
import base64
import logging
import os
import mimetypes
import httpx
from typing import Dict, Any, List, Optional
from telethon import TelegramClient
from src.settings import settings

logger = logging.getLogger(__name__)


class CasePublisher:
    """Service to automatically process portfolio cases from @jonbranding Telegram channel and upload them to CMS/n8n."""

    def __init__(self, client: TelegramClient, db=None):
        self.client = client
        self.db = db
        self.temp_media_dir = os.path.join("data", "tmp", "cases")
        os.makedirs(self.temp_media_dir, exist_ok=True)

        # AI Config
        from google import genai

        self.genai_client = genai.Client(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )
        self.model_name = os.getenv("GEMINI_CASE_PUBLISHER_MODEL", settings.GEMINI_CALL_MODEL)

    async def is_portfolio_case(self, text: str) -> bool:
        """Use Gemini to detect if the Telegram post represents a design/branding portfolio case."""
        if not text or len(text.strip()) < 50:
            return False

        prompt = (
            "Determine if the following Telegram channel post is a portfolio showcase, brand keys/case, "
            "or client project design presentation of Jon Branding agency in Uzbek. "
            "It usually contains details about brand design, packaging design, logo creation, client details, "
            "or showcase of visual identity.\n"
            "Respond with only 'YES' or 'NO'.\n\n"
            f"Post text:\n{text}"
        )

        try:
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.genai_client, prompt=prompt, model=self.model_name
            )
            ans = (response.text or "").strip().upper()
            return "YES" in ans
        except Exception as e:
            logger.error(f"[CASE_PUBLISHER] Case classification error: {e}")
            # Fallback to simple keyword checklist
            keywords = ["keys", "case", "brending", "dizayn", "mijoz", "logo", "qadoq"]
            return any(k in text.lower() for k in keywords)

    async def extract_case_details(self, text: str) -> Dict[str, Any]:
        """Extract structured case details in Uzbek using Gemini JSON capability."""
        prompt = (
            "Analyze the following portfolio case text in Uzbek and extract the structured details. "
            "Ensure the output is valid JSON, strictly complying with the following structure:\n"
            "{\n"
            '  "title": "A short, descriptive case title in Uzbek",\n'
            '  "client": "Client name or project name (e.g. Brand Name)",\n'
            '  "short_description": "A 1-2 sentence hook / summary in Uzbek",\n'
            '  "challenge": "What was the brand problem, request or challenge in Uzbek?",\n'
            '  "solution": "What was Jon Branding\'s creative solution or design path in Uzbek?",\n'
            '  "results": "What are the results, customer feedback or impact in Uzbek? (N/A if not found)",\n'
            '  "tags": ["branding", "packaging", "logo", "web", "identity"]\n'
            "}\n\n"
            f"Case text:\n{text}"
        )

        try:
            from google.genai import types

            response = await asyncio.to_thread(
                self.genai_client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = (response.text or "").strip()
            import json

            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"[CASE_PUBLISHER] Case extraction error: {e}")
            # Safe fallback structure
            return {
                "title": "Jon Branding Portfolio Keys",
                "client": "N/A",
                "short_description": text[:150] + "...",
                "challenge": "N/A",
                "solution": text,
                "results": "N/A",
                "tags": ["branding"],
            }

    async def download_message_media(self, message) -> List[str]:
        """Download all photo attachments from the Telegram message. Returns list of local file paths."""
        downloaded_paths = []
        if not message or not message.media:
            return downloaded_paths

        # If it's a grouped message, Telethon might need to gather album media,
        # but for simple message listener, we download what's in the message.
        try:
            if getattr(message, "photo", None) or getattr(message, "document", None):
                # Standard download
                filename = f"media_{message.id}_{int(asyncio.get_event_loop().time())}"
                path = await self.client.download_media(message, file=os.path.join(self.temp_media_dir, filename))
                if path and os.path.exists(path):
                    downloaded_paths.append(path)
                    logger.info(f"[CASE_PUBLISHER] Downloaded media for msg {message.id}: {path}")
        except Exception as e:
            logger.error(f"[CASE_PUBLISHER] Media download error for msg {message.id}: {e}")

        return downloaded_paths

    async def publish_case(self, case_data: Dict[str, Any], image_paths: List[str]) -> bool:
        """Encode images as Base64 and send the structured case payload to settings.CMS_WEBHOOK_URL."""
        webhook_url = os.environ.get("CMS_WEBHOOK_URL") or settings.CMS_WEBHOOK_URL
        if not webhook_url:
            logger.warning("[CASE_PUBLISHER] CMS_WEBHOOK_URL is not set. Skipping push to CMS.")
            return False

        # Prepare encoded images list
        encoded_images = []
        for path in image_paths:
            try:
                if not os.path.exists(path):
                    continue
                with open(path, "rb") as img_file:
                    b64_data = base64.b64encode(img_file.read()).decode("utf-8")
                
                filename = os.path.basename(path)
                mime_type, _ = mimetypes.guess_type(path)
                encoded_images.append({
                    "filename": filename,
                    "mime_type": mime_type or "image/jpeg",
                    "content_type": mime_type or "image/jpeg",
                    "data": b64_data
                })
            except Exception as e:
                logger.error(f"[CASE_PUBLISHER] Image encoding error for {path}: {e}")

        # Assemble final payload
        payload = {
            "source": "telegram_channel",
            "channel": settings.JONBRANDING_CHANNEL,
            "case": case_data,
            "images": encoded_images
        }

        # Dispatch via HTTP POST
        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                response = await http_client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code in (200, 201, 202):
                    logger.info(f"✅ [CASE_PUBLISHER] Successfully published case '{case_data.get('title')}' to CMS.")
                    return True
                else:
                    logger.error(
                        f"❌ [CASE_PUBLISHER] CMS Webhook returned error code {response.status_code}: {response.text}"
                    )
        except Exception as e:
            logger.error(f"❌ [CASE_PUBLISHER] Failed to dispatch webhook to CMS: {e}")

        return False

    async def process_message(self, message) -> bool:
        """Main orchestrator for a single Telegram channel message."""
        text = message.text or ""
        if not text:
            return False

        # 1. Classify if it's a portfolio case
        is_case = await self.is_portfolio_case(text)
        if not is_case:
            logger.info(f"[CASE_PUBLISHER] Message {message.id} classified as non-case. Skipping.")
            return False

        logger.info(f"🚀 [CASE_PUBLISHER] Processing portfolio case from message {message.id}...")

        # 2. Extract structured details using AI
        case_data = await self.extract_case_details(text)

        # 3. Download media attachments
        image_paths = await self.download_message_media(message)

        # 4. Push payload to CMS
        success = await self.publish_case(case_data, image_paths)

        # Clean up temporary media files to conserve workspace disk space
        for path in image_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as ce:
                logger.warning(f"[CASE_PUBLISHER] Cleanup failed for {path}: {ce}")

        return success
