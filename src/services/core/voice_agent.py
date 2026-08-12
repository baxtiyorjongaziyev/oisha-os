import httpx
import logging
from typing import Optional, Dict, Any
from src.settings import settings

logger = logging.getLogger(__name__)

async def trigger_voice_agent(lead_name: str, phone_number: str, context: Optional[str] = None) -> bool:
    """
    Triggers an outbound phone call via Vapi.ai for a new lead.
    Returns True if the call was successfully queued, False otherwise.
    """
    if not settings.VAPI_API_KEY:
        logger.info("VAPI_API_KEY is not set. Voice Agent is currently disabled.")
        return False
        
    if not phone_number:
        logger.warning(f"Voice Agent failed: No phone number provided for {lead_name}")
        return False

    vapi_key = settings.VAPI_API_KEY.get_secret_value()
    phone_id = settings.VAPI_PHONE_NUMBER_ID or ""

    # This is a sample Vapi.ai outbound call payload
    payload: Dict[str, Any] = {
        "phoneNumberId": phone_id,
        "customer": {
            "number": phone_number,
            "name": lead_name
        },
        "assistant": {
            "name": "Oisha",
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are Oisha, a surgical assistant for Jon Branding. You are calling {lead_name} who recently left a request. Find out their branding needs. Context: {context or 'None'}"
                    }
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "flq6f7yk4E4fJM5XTYuZ"
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vapi.ai/call",
                json=payload,
                headers={"Authorization": f"Bearer {vapi_key}"},
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Successfully triggered Voice Agent for {lead_name} ({phone_number})")
            return True
    except Exception as e:
        logger.error(f"Failed to trigger Voice Agent for {lead_name}: {e}")
        return False

def init_voice_agent():
    pass
