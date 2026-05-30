import inspect
import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.settings import settings

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - optional at runtime in degraded installs
    genai = None
    genai_types = None

try:
    from telethon import functions, types
except Exception:  # pragma: no cover - optional for bot-only runtimes
    functions = None
    types = None

logger = logging.getLogger(__name__)


def normalize_phone(phone: Optional[str]) -> str:
    """Normalize UZ/common phone strings to +<digits> for matching."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return f"+{digits}"


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _secret_to_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value or "").strip()


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _extract_text_from_history_item(item: Dict[str, Any]) -> str:
    if "parts" in item:
        parts = item.get("parts") or []
        if parts and isinstance(parts[0], dict):
            return str(parts[0].get("text") or "").strip()
    return str(
        item.get("message_text")
        or item.get("text")
        or item.get("message")
        or ""
    ).strip()


def _extract_role_from_history_item(item: Dict[str, Any]) -> str:
    role = str(item.get("role") or "").lower()
    if role == "model":
        return "Oisha"
    if role == "assistant":
        return "Oisha"
    if item.get("is_ai") or item.get("is_ai_reply"):
        return "Oisha"
    return "Mijoz"


@dataclass
class LeadEnrichmentResult:
    status: str
    lead_id: int
    phone: str = ""
    telegram_user_id: Optional[int] = None
    note_added: bool = False
    reason: Optional[str] = None
    tags_added: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "lead_id": self.lead_id,
            "phone": self.phone,
            "telegram_user_id": self.telegram_user_id,
            "note_added": self.note_added,
            "reason": self.reason,
            "tags_added": list(self.tags_added),
        }


class AmoCRMLeadEnricher:
    """Build and write a client intelligence note for AmoCRM leads.

    The service uses, in order:
    1. Local DB contact and message history.
    2. Telegram userbot phone lookup when available.
    3. Gemini summary when configured, with deterministic fallback.
    """

    def __init__(
        self,
        amocrm: Any,
        db: Any = None,
        user_client: Any = None,
        gemini_api_key: Optional[str] = None,
        message_limit: Optional[int] = None,
        refresh_hours: Optional[int] = None,
        model_name: str = "gemini-2.0-flash",
    ):
        self.amocrm = amocrm
        self.db = db
        self.user_client = user_client
        self.message_limit = int(
            message_limit
            if message_limit is not None
            else getattr(settings, "AMOCRM_ENRICHMENT_MESSAGE_LIMIT", 20)
        )
        self.refresh_hours = int(
            refresh_hours
            if refresh_hours is not None
            else getattr(settings, "AMOCRM_ENRICHMENT_REFRESH_HOURS", 24)
        )
        self.model_name = model_name

        api_key = (gemini_api_key or _secret_to_text(settings.GEMINI_API_KEY)).strip()
        self.genai_client = None
        if api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("[AMO_ENRICH] Gemini client init skipped: %s", exc)

    async def enrich_lead(
        self,
        lead_id: int,
        lead_data: Optional[Dict[str, Any]] = None,
        phone: Optional[str] = None,
        force: bool = False,
    ) -> LeadEnrichmentResult:
        lead_data = lead_data or {}
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            return LeadEnrichmentResult(
                status="skipped",
                lead_id=int(lead_id),
                reason="phone_missing",
            )

        if not force and await self._recently_enriched(int(lead_id), normalized_phone):
            return LeadEnrichmentResult(
                status="skipped",
                lead_id=int(lead_id),
                phone=normalized_phone,
                reason="recently_enriched",
            )

        profile = await self._find_telegram_profile(normalized_phone)
        telegram_user_id = self._profile_user_id(profile)
        messages = await self._collect_messages(telegram_user_id)
        analysis = await self._build_analysis(
            lead_data=lead_data,
            phone=normalized_phone,
            profile=profile,
            messages=messages,
        )
        note = self._format_note(
            lead_id=int(lead_id),
            lead_data=lead_data,
            phone=normalized_phone,
            profile=profile,
            messages=messages,
            analysis=analysis,
        )

        note_result = await maybe_await(self.amocrm.add_lead_note(int(lead_id), note))
        note_added = bool(note_result)
        tags_added: List[str] = []

        if note_added:
            tags_added = await self._add_tags(int(lead_id), profile)
            await self._mark_enriched(
                lead_id=int(lead_id),
                phone=normalized_phone,
                telegram_user_id=telegram_user_id,
                message_count=len(messages),
            )

        return LeadEnrichmentResult(
            status="enriched" if note_added else "failed",
            lead_id=int(lead_id),
            phone=normalized_phone,
            telegram_user_id=telegram_user_id,
            note_added=note_added,
            reason=None if note_added else "note_add_failed",
            tags_added=tags_added,
        )

    async def _recently_enriched(self, lead_id: int, phone: str) -> bool:
        if not self.db or self.refresh_hours <= 0:
            return False
        try:
            raw = await self.db.get_state(self._state_key(lead_id), "")
            if not raw:
                return False
            data = json.loads(raw)
            if normalize_phone(data.get("phone")) != phone:
                return False
            updated_at = data.get("updated_at")
            if not updated_at:
                return False
            dt = datetime.fromisoformat(str(updated_at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return age_hours < self.refresh_hours
        except Exception as exc:
            logger.debug("[AMO_ENRICH] State read skipped: %s", exc)
            return False

    async def _mark_enriched(
        self,
        lead_id: int,
        phone: str,
        telegram_user_id: Optional[int],
        message_count: int,
    ) -> None:
        if not self.db:
            return
        payload = {
            "phone": phone,
            "telegram_user_id": telegram_user_id,
            "message_count": message_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.db.set_state(
                self._state_key(lead_id), json.dumps(payload, ensure_ascii=False)
            )
        except Exception as exc:
            logger.debug("[AMO_ENRICH] State write skipped: %s", exc)

    @staticmethod
    def _state_key(lead_id: int) -> str:
        return f"amocrm_lead_enrichment:{lead_id}"

    async def _find_telegram_profile(self, phone: str) -> Dict[str, Any]:
        profile: Dict[str, Any] = {}

        if self.db:
            try:
                db_user = await self.db.get_user_by_phone(phone)
                if db_user:
                    profile.update(db_user)
                    profile["source"] = "db"
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB phone lookup skipped: %s", exc)

        if self._profile_user_id(profile) or not self.user_client:
            return profile

        user = await self._lookup_userbot_by_phone(phone)
        if not user:
            return profile

        profile.update(user)
        profile["source"] = "userbot"
        if self.db:
            try:
                await self.db.upsert_user(
                    user_id=int(user["user_id"]),
                    first_name=user.get("first_name") or "Telegram user",
                    username=user.get("username"),
                    phone=phone,
                    last_name=user.get("last_name"),
                )
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB upsert skipped: %s", exc)
        return profile

    async def _lookup_userbot_by_phone(self, phone: str) -> Dict[str, Any]:
        if functions is None or types is None:
            return {}

        try:
            is_authorized = True
            if hasattr(self.user_client, "is_user_authorized"):
                is_authorized = bool(
                    await maybe_await(self.user_client.is_user_authorized())
                )
            if not is_authorized:
                return {}

            clean_phone = phone.replace("+", "")
            contact = types.InputPhoneContact(
                client_id=random.randrange(-(2**63), 2**63),
                phone=clean_phone,
                first_name="Oisha Lookup",
                last_name="",
            )
            result = await self.user_client(
                functions.contacts.ImportContactsRequest(contacts=[contact])
            )
            users = getattr(result, "users", None) or []
            if not users:
                return {}
            imported = getattr(result, "imported", None) or []

            user = users[0]
            user_id = getattr(user, "id", None)
            data = {
                "user_id": int(user_id) if user_id is not None else None,
                "username": getattr(user, "username", None),
                "first_name": getattr(user, "first_name", None),
                "last_name": getattr(user, "last_name", None),
                "phone": phone,
            }

            if user_id is not None and imported:
                try:
                    await self.user_client(
                        functions.contacts.DeleteContactsRequest(id=[int(user_id)])
                    )
                except Exception:
                    pass
            return {k: v for k, v in data.items() if v is not None}
        except Exception as exc:
            logger.warning("[AMO_ENRICH] Userbot phone lookup failed: %s", exc)
            return {}

    async def _collect_messages(
        self, telegram_user_id: Optional[int]
    ) -> List[Dict[str, str]]:
        if not telegram_user_id:
            return []

        messages: List[Dict[str, str]] = []
        if self.db:
            try:
                history = await self.db.get_recent_messages(
                    int(telegram_user_id), limit=self.message_limit
                )
                for item in history or []:
                    if not isinstance(item, dict):
                        continue
                    text = _extract_text_from_history_item(item)
                    if not text:
                        continue
                    messages.append(
                        {
                            "role": _extract_role_from_history_item(item),
                            "text": _clip(text, 800),
                            "created_at": str(item.get("created_at") or ""),
                        }
                    )
            except Exception as exc:
                logger.debug("[AMO_ENRICH] DB history skipped: %s", exc)

        if messages or not self.user_client:
            return messages[-self.message_limit :]

        try:
            async for msg in self.user_client.iter_messages(
                int(telegram_user_id), limit=self.message_limit
            ):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                messages.append(
                    {
                        "role": "Oisha" if getattr(msg, "out", False) else "Mijoz",
                        "text": _clip(text, 800),
                        "created_at": str(getattr(msg, "date", "") or ""),
                    }
                )
        except Exception as exc:
            logger.debug("[AMO_ENRICH] Userbot history skipped: %s", exc)

        return list(reversed(messages))[-self.message_limit :]

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
                response = await self.genai_client.aio.models.generate_content(**kwargs)
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

    @staticmethod
    def _profile_user_id(profile: Dict[str, Any]) -> Optional[int]:
        value = profile.get("user_id") or profile.get("id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _display_name(profile: Dict[str, Any]) -> str:
        return " ".join(
            str(part).strip()
            for part in (
                profile.get("first_name") or profile.get("contact_name"),
                profile.get("last_name"),
            )
            if part
        ).strip()
