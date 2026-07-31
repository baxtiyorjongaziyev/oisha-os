import asyncio
import structlog
import httpx
from typing import Dict, Any, Optional
from src.settings import settings

logger = structlog.get_logger()


class VoiceAgent:
    """🎙 AI Voice Agents — Vapi.ai orqali leadlarga avtomatik qo'ng'iroq.

    Ishlash tartibi:
    1. AmoCRM ga yangi lead tushadi
    2. Oisha webhook orqali sezadi
    3. VoiceAgent.qualify_lead(lead_info) chaqiriladi
    4. Vapi.ai ga qo'ng'iroq buyrug'i yuboriladi
    5. Vapi.ai mijozga O'zbek tilida qo'ng'iroq qiladi
    6. Suhbat natijasi webhook orqali qaytadi
    7. Oisha natijani AmoCRM lead ga yozadi
    """

    def __init__(self):
        self.api_key = settings.VAPI_API_KEY.get_secret_value() if settings.VAPI_API_KEY else None
        self.agent_id = settings.VAPI_AGENT_ID
        self.public_key = settings.VAPI_PUBLIC_KEY.get_secret_value() if settings.VAPI_PUBLIC_KEY else None
        self.enabled = settings.ENABLE_VOICE_AGENT and bool(self.api_key)
        self.base_url = "https://api.vapi.ai"

    async def qualify_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Lead ga qo'ng'iroq qilish va saralash."""
        if not self.enabled:
            return {"status": "disabled", "message": "Voice agent disabled"}

        phone = self._extract_phone(lead)
        if not phone:
            return {"status": "skipped", "reason": "No phone number"}

        name = lead.get("name", "Mijoz")
        payload = {
            "agentId": self.agent_id,
            "phoneNumber": phone,
            "assistantOverrides": {
                "firstMessage": f"Assalomu alaykum, {name}! Men Jon Branding agentligining virtual yordamchisiman. Sizning so'rovingiz bo'yicha qo'ng'iroq qilyapman. Loyihangiz haqida qisqacha ma'lumot bersangiz?",
                "model": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Siz Jon Branding agentligining AI yordamchisisiz. "
                                "Vazifangiz mijozni saralash (qualify): "
                                "1. Mijozning kompaniya nomi va sohasini aniqlang\n"
                                "2. Qanday xizmat kerakligini bilib oling (brending, logotip, veb-sayt, qadoq)\n"
                                "3. Byudjet haqida ma'lumot oling\n"
                                "4. Mijozning telefon raqami va Telegram ini tasdiqlang\n"
                                "5. Qisqa va aniq gaplashing, mijozni charchatmang\n"
                                "Suhbat yakunida natijani JSON formatda qaytaring."
                            ),
                        }
                    ],
                },
            },
            "metadata": {
                "source": "oisha-os",
                "lead_id": lead.get("id"),
                "lead_name": name,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/call",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info("[VOICE] Call initiated", lead=name, call_id=data.get("id"))
                    return {"status": "called", "call_id": data.get("id")}
                logger.warning("[VOICE] Vapi API error", status=resp.status_code, body=resp.text)
                return {"status": "error", "message": resp.text}
        except Exception as e:
            logger.error("[VOICE] Failed to initiate call", error=str(e))
            return {"status": "error", "message": str(e)}

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Vapi.ai webhook imzosini tekshirish."""
        if not self.public_key or not signature:
            return False
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend

            public_key_obj = serialization.load_pem_public_key(
                f"-----BEGIN PUBLIC KEY-----\n{self.public_key}\n-----END PUBLIC KEY-----".encode(),
                backend=default_backend(),
            )
            public_key_obj.verify(
                bytes.fromhex(signature),
                payload,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.warning("[VOICE] Signature verification failed", error=str(e))
            return False

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Vapi.ai dan qaytgan webhook natijasini qayta ishlash.

        Payload tarkibi:
        {
            "call_id": "...",
            "status": "completed|failed|in_progress",
            "analysis": {
                "summary": "...",
                "structured": {
                    "company": "...",
                    "service_needed": "...",
                    "budget": "...",
                    "contact_confirmed": true/false,
                    "qualified": true/false
                }
            },
            "metadata": {"lead_id": "..."}
        }
        """
        call_id = payload.get("call_id")
        status = payload.get("status")
        analysis = payload.get("analysis", {})
        summary = analysis.get("summary", "")
        structured = analysis.get("structured", {})
        metadata = payload.get("metadata", {})
        lead_id = metadata.get("lead_id")

        result = {
            "status": status,
            "lead_id": lead_id,
            "call_id": call_id,
            "summary": summary,
            "structured": structured,
            "qualified": structured.get("qualified", False),
        }

        logger.info("[VOICE] Webhook received", **result)
        return result

    def _extract_phone(self, lead: Dict[str, Any]) -> Optional[str]:
        """AmoCRM lead dan telefon raqamni chiqarish."""
        for cf in lead.get("custom_fields_values") or []:
            if cf.get("field_code") == "PHONE":
                values = cf.get("values", [])
                if values:
                    return values[0].get("value")
        return lead.get("phone")