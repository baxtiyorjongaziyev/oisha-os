"""
Gemini AI summary generation, objection extraction, and AmoCRM note formatting mixin.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

try:
    from google.genai import types as genai_types
except ImportError:
    genai_types = None

from src.services.core.crm.enrichment.models import _clip, maybe_await
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = logging.getLogger("AmoCRMLeadEnrichment")


class AiSynthesizerMixin:
    """Generates AI insights and formats CRM enrichment notes."""

    async def _build_analysis(
        self,
        lead_data: Dict[str, Any],
        phone: str,
        profile: Dict[str, Any],
        messages: List[Dict[str, str]],
    ) -> str:
        if self.genai_client:
            prompt = self._analysis_prompt(lead_data, phone, profile, messages)
            try:
                kwargs: Dict[str, Any] = {"model": self.model_name, "contents": [prompt]}
                if genai_types is not None:
                    kwargs["config"] = genai_types.GenerateContentConfig(
                        max_output_tokens=900
                    )
                response, _ = await generate_content_with_fallback(
                    self.genai_client,
                    primary_model=self.model_name,
                    contents=kwargs["contents"],
                    config=kwargs.get("config"),
                    env_name="GEMINI_ENRICHMENT_FALLBACK_MODELS",
                    log_prefix="[AMO_ENRICH]",
                )
                text = str(getattr(response, "text", "") or "").strip()
                if text:
                    return _clip(text, 3500)
            except Exception as exc:
                logger.warning("[AMO_ENRICH] Gemini analysis failed: %s", exc)

        return self._fallback_analysis(lead_data, profile, messages)

    def _analysis_prompt(
        self,
        lead_data: Dict[str, Any],
        phone: str,
        profile: Dict[str, Any],
        messages: List[Dict[str, str]],
    ) -> str:
        context = {
            "lead": {
                "id": lead_data.get("id"),
                "name": lead_data.get("name"),
                "status_id": lead_data.get("status_id"),
                "pipeline_id": lead_data.get("pipeline_id"),
                "price": lead_data.get("price"),
            },
            "phone": phone,
            "telegram_profile": profile,
            "recent_messages": messages[-self.message_limit :],
        }
        return (
            "Siz amoCRM uchun mijoz profili yozuvchi Oisha analizchisiz. "
            "Faqat berilgan faktlarga tayangan holda Uzbek latinida qisqa, lekin "
            "amaliy note yozing. Tuzilma: 1) Mijoz kim, 2) ehtiyoj/qiziqish, "
            "3) suhbat holati, 4) risklar, 5) menejer uchun keyingi qadam. "
            "Taxminlarni 'taxmin' deb belgilang, maxfiy yoki topilmagan "
            "ma'lumotni uydirmang.\n\n"
            f"Kontekst JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        )

    def _fallback_analysis(
        self,
        lead_data: Dict[str, Any],
        profile: Dict[str, Any],
        messages: List[Dict[str, str]],
    ) -> str:
        name = self._display_name(profile) or str(lead_data.get("name") or "Noma'lum")
        client_messages = [m["text"] for m in messages if m.get("role") == "Mijoz"]
        text_blob = " ".join(client_messages).lower()
        interests = []
        for keyword in ("branding", "logo", "sayt", "dizayn", "marketing", "smm"):
            if keyword in text_blob:
                interests.append(keyword)
        last_client = client_messages[-1] if client_messages else ""
        interest_text = ", ".join(interests) if interests else "aniq signal topilmadi"

        return "\n".join(
            [
                f"Mijoz: {name}",
                f"Qiziqish/ehtiyoj: {interest_text}.",
                f"Suhbat holati: {len(messages)} ta oxirgi xabar topildi.",
                f"Oxirgi mijoz signali: {_clip(last_client, 500) or 'history topilmadi'}.",
                "Risk: ma'lumot cheklangan bo'lsa, avval ehtiyoj, budjet va muddatni aniqlash kerak.",
                "Keyingi qadam: menejer 1 ta aniq savol bilan brif yoki uchrashuvga olib kirsin.",
            ]
        )

    def _format_note(
        self,
        lead_id: int,
        lead_data: Dict[str, Any],
        phone: str,
        profile: Dict[str, Any],
        messages: List[Dict[str, str]],
        analysis: str,
    ) -> str:
        username = str(profile.get("username") or "").strip()
        user_id = self._profile_user_id(profile)
        tg_line = "topilmadi"
        if username:
            tg_line = f"@{username}"
        if user_id:
            tg_line = f"{tg_line} | tg://user?id={user_id}"

        recent_lines = []
        for msg in messages[-5:]:
            recent_lines.append(
                f"- {msg.get('role', 'Mijoz')}: {_clip(msg.get('text', ''), 240)}"
            )
        recent_text = "\n".join(recent_lines) if recent_lines else "- history topilmadi"

        note = f"""
[Oisha Client Intelligence]
Lead ID: {lead_id}
Lead nomi: {lead_data.get('name') or "Noma'lum"}
Telefon: {phone}
Telegram: {tg_line}
Manba: {profile.get('source') or 'amoCRM phone'}

AI analiz:
{analysis}

Oxirgi kontekst:
{recent_text}

Auto-note: telefon raqam asosida DB/userbot konteksti tekshirildi.
""".strip()
        return _clip(note, 9000)

    async def _add_tags(self, lead_id: int, profile: Dict[str, Any]) -> List[str]:
        tags = ["Oisha analyzed"]
        if self._profile_user_id(profile):
            tags.append("Telegram matched")

        added: List[str] = []
        add_tag = getattr(self.amocrm, "add_lead_tag", None)
        if not callable(add_tag):
            return added

        for tag in tags:
            try:
                result = await maybe_await(add_tag(lead_id, tag))
                if result:
                    added.append(tag)
            except Exception as exc:
                logger.debug("[AMO_ENRICH] Tag add skipped: %s", exc)
        return added

