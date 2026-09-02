import logging
import os
import json
import httpx
from typing import Dict, Any

from src.settings import settings

logger = logging.getLogger(__name__)


class SanityPublisher:
    """Service to automatically generate and publish case studies to CMS when AmoCRM projects are completed."""

    def __init__(self, amocrm=None, genai_client=None):
        self.amocrm = amocrm
        self.genai_client = genai_client

        if self.genai_client is None:
            api_key = (settings.GEMINI_API_KEY.get_secret_value() or "").strip()
            if api_key:
                try:
                    from google import genai
                    self.genai_client = genai.Client(api_key=api_key)
                except Exception as exc:
                    logger.warning("[SANITY_PUBLISHER] Gemini client init skipped: %s", exc)
            else:
                logger.warning("[SANITY_PUBLISHER] GEMINI_API_KEY missing.")
        
        self.model_name = os.getenv("GEMINI_CASE_PUBLISHER_MODEL", settings.GEMINI_CALL_MODEL)

    async def generate_case_study(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a structured portfolio case study using Gemini based on AmoCRM lead data."""
        lead_name = lead_data.get("name", "N/A")
        price = lead_data.get("price", 0)
        custom_fields = lead_data.get("custom_fields_values", [])
        
        # Serialize lead data to a readable string for the prompt
        lead_context = f"Lead Name: {lead_name}\nPrice/Budget: {price}\n"
        if custom_fields:
            for field in custom_fields:
                field_name = field.get("field_name")
                values = [v.get("value") for v in field.get("values", [])]
                lead_context += f"{field_name}: {', '.join(map(str, values))}\n"

        prompt = (
            "You are a professional copywriter for Jon Branding agency. "
            "A project has just been marked as 'Won' (Yakunlandi) in AmoCRM. "
            "Based on the following CRM lead data, write a short, professional portfolio case study in Uzbek. "
            "Ensure the output is valid JSON, strictly complying with the following structure:\n"
            "{\n"
            '  "title": "A short, descriptive case title in Uzbek",\n'
            '  "client": "Client name (infer from lead name or fields)",\n'
            '  "short_description": "A 1-2 sentence hook / summary in Uzbek",\n'
            '  "challenge": "What was the presumed problem or request based on this data? (in Uzbek)",\n'
            '  "solution": "What was Jon Branding\'s solution? (in Uzbek)",\n'
            '  "results": "What is the final result? (in Uzbek)",\n'
            '  "tags": ["branding", "design", "portfolio"]\n'
            "}\n\n"
            f"AmoCRM Lead Data:\n{lead_context}"
        )

        try:
            from google.genai import types
            from src.services.utils.gemini_fallback import generate_content_with_fallback

            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.4,
                ),
                env_name="GEMINI_CASE_PUBLISHER_FALLBACK_MODELS",
                log_prefix="[SANITY_PUBLISHER]",
            )
            raw_text = (response.text or "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"[SANITY_PUBLISHER] Case generation error: {e}")
            return {
                "title": f"Loyiha: {lead_name}",
                "client": lead_name,
                "short_description": "Loyiha muvaffaqiyatli yakunlandi.",
                "challenge": "N/A",
                "solution": "N/A",
                "results": "Loyiha tugatildi va topshirildi.",
                "tags": ["amo-crm-import"],
            }

    async def publish_case_from_amocrm(self, lead_id: int, lead_data: Dict[str, Any]) -> bool:
        """Main orchestrator: Called when AmoCRM webhook fires a 'Won' status."""
        logger.info(f"🚀 [SANITY_PUBLISHER] Processing completed project from AmoCRM lead {lead_id}...")
        
        # 1. Generate Case Study Content
        case_data = await self.generate_case_study(lead_data)
        case_data["amocrm_lead_id"] = lead_id

        # 2. Publish to CMS Webhook
        webhook_url = os.environ.get("CMS_WEBHOOK_URL") or settings.CMS_WEBHOOK_URL
        if not webhook_url:
            logger.warning("[SANITY_PUBLISHER] CMS_WEBHOOK_URL is not set. Case generated but not published. Data: %s", case_data)
            return False

        payload = {
            "source": "amocrm_completed_project",
            "case": case_data,
            "images": []  # AmoCRM usually doesn't provide case images directly via webhook
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code in (200, 201, 202):
                    logger.info(f"✅ [SANITY_PUBLISHER] Successfully published case '{case_data.get('title')}' to CMS.")
                    return True
                else:
                    logger.error(
                        f"❌ [SANITY_PUBLISHER] CMS Webhook returned error code {response.status_code}: {response.text}"
                    )
        except Exception as e:
            logger.error(f"❌ [SANITY_PUBLISHER] Failed to dispatch webhook to CMS: {e}")

        return False
