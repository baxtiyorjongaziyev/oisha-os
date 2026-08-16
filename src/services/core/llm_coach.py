import structlog
from typing import Any, Dict, List, Optional

from src.services.utils.free_ai_router import get_free_ai_router

logger = structlog.get_logger()


class SalesCoachLLM:
    """LLM wrapper for SalesCoach real‑time tip generation.

    The public API matches ``tests/test_llm_coach.py`` – it is an *async class
    method* that receives a ``transcript`` string, optional ``segments`` and an
    optional ``context`` dict (which may contain ``crm_status``). It returns a
    JSON‑decoded ``dict`` or ``None`` on failure.
    """

    @classmethod
    async def generate_tip(
        cls,
        transcript: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        # Obtain a fresh router for each call – this makes the function easy to
        # mock in tests (the router will be replaced by the patched mock).
        router = get_free_ai_router()
        crm_status = ""
        if isinstance(context, dict):
            crm_status = context.get("crm_status", "")

        prompt_template = (
            "{\n"
            "  \"role\": \"assistant\",\n"
            "  \"content\": \"You are a sales‑coach AI. Analyze the provided "
            "conversation snippet and the current CRM status, then generate a "
            "single helpful tip for the sales representative.\n\n"
            "  Use the following JSON schema for the response: {\\\"tip\\\": \\\"<your tip>\\\"}.\n\n"
            "  Input variables: message (str), crm_status (str), segments (list of dict). "
            "Return ONLY the JSON object.\"\n"
            "}\n"
        )

        variables = {
            "message": transcript,
            "crm_status": crm_status,
            "segments": segments or [],
        }
        try:
            response = await router.generate_content(
                prompt=prompt_template,
                model_name="gemini-1.5-flash",
                streaming=False,
                variables=variables,
                json_mode=True,
            )
            if hasattr(response, "text"):
                response = response.text
            if isinstance(response, dict):
                result = response
            elif isinstance(response, str):
                import json
                result = json.loads(response)
            elif hasattr(response, "text"):
                import json
                result = json.loads(response.text)
            else:
                return None
            # Truncate overly long tip strings to 200 characters (test expects).
            tip = result.get("tip")
            if isinstance(tip, str) and len(tip) > 200:
                result["tip"] = tip[:200]
            return result
        except Exception as exc:
            logger.warning("[LLMCoach] tip generation failed: %s", type(exc).__name__)
            return None
