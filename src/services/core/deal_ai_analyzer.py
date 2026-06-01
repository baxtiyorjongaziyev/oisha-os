"""AmoCRM Deal AI Analyzer.

Har bir aktiv Sdelka (lead) uchun:
1. AmoCRM dan lead va biriktirilgan contact ma'lumotlarini oladi.
2. Contact'dagi telefon / @username orqali Telegram suhbat ID sini topadi.
3. Telethon userbot orqali oxirgi N ta xabarni oladi.
4. Gemini yoki Claude orqali suhbatni klassifikatsiya qiladi:
   REAL_CLIENT | JUNK | PERSONAL | SPAM | TEST | UNCLEAR
5. AmoCRM ga teg + tushuntiruvchi izoh + (ixtiyoriy) review task qo'shadi.

Hech narsa o'chirilmaydi. Asosiy tamoyil: biz faqat tushuntiramiz va
foydalanuvchi xulosa qiladi.

Foydalanish:
    analyzer = DealAIAnalyzer(amocrm, tg_client, ai_callable)
    report = await analyzer.run(limit=50, dry_run=True)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
USERNAME_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{5,32})")

CATEGORY_TAGS = {
    "REAL_CLIENT": "OISHA_AI_REAL_CLIENT",
    "JUNK": "OISHA_AI_JUNK",
    "PERSONAL": "OISHA_AI_PERSONAL",
    "SPAM": "OISHA_AI_SPAM",
    "TEST": "OISHA_AI_TEST_DEAL",
    "UNCLEAR": "OISHA_AI_UNCLEAR",
}

CATEGORY_LABEL_UZ = {
    "REAL_CLIENT": "Haqiqiy mijoz",
    "JUNK": "Bekorchi / keraksiz",
    "PERSONAL": "Shaxsiy aloqa",
    "SPAM": "Spam / noto'g'ri raqam",
    "TEST": "Test yoki ichki sdelka",
    "UNCLEAR": "Aniq emas, ko'rib chiqing",
}


ANALYZER_PROMPT = """Sen Jon Branding agentligi uchun ishlovchi AmoCRM auditor agentisan.
Sening vazifang — bitta sdelkani (lead) tahlil qilib, uning ahamiyatini
quyidagi 6 ta kategoriyadan biriga ajratish:

REAL_CLIENT — haqiqiy mijoz, sotuv potensiali bor
JUNK        — bekorchi sdelka, hech qanday tijoriy qiymat yo'q
PERSONAL    — shaxsiy aloqa (oila, do'st, qarindosh)
SPAM        — spam, noto'g'ri raqam yoki bot
TEST        — ichki test sdelka yoki dublikat
UNCLEAR     — yetarli ma'lumot yo'q

Sen quyidagilarni hisobga olasan:
- Sdelka nomi va statusi
- AmoCRM dagi izohlar va custom fieldlar
- Telegram suhbatdan oxirgi xabarlar (agar mavjud)

JSON formatida javob ber, qo'shimcha matn yozma:

{
  "category": "REAL_CLIENT|JUNK|PERSONAL|SPAM|TEST|UNCLEAR",
  "confidence": 0.0,            // 0-1 oraliqda
  "reason": "qisqacha sabab (1 jumla, o'zbek tilida)",
  "evidence": ["dalil 1", "dalil 2"],  // ko'pi bilan 4 ta
  "recommended_action": "qisqa tavsiya (1 jumla)"
}
"""


@dataclass
class DealAnalysis:
    lead_id: int
    lead_name: str
    pipeline_id: Optional[int] = None
    status_id: Optional[int] = None
    category: str = "UNCLEAR"
    confidence: float = 0.0
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = ""
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None
    telegram_phone: Optional[str] = None
    messages_sampled: int = 0
    tag_applied: Optional[str] = None
    note_applied: bool = False
    status: str = "analyzed"  # analyzed | dry_run | applied | error | skipped


@dataclass
class AnalyzerReport:
    generated_at: str
    checked: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    dry_run: bool = True
    items: List[DealAnalysis] = field(default_factory=list)


class DealAIAnalyzer:
    """Analyze AmoCRM deals using Telegram context and an AI classifier."""

    def __init__(
        self,
        amocrm: Any,
        tg_client: Any,
        ai_call: Callable[[str], Awaitable[str]],
        message_window: int = 30,
        rate_limit_sec: float = 0.8,
    ):
        """
        Args:
            amocrm: AmoCRMSync instance
            tg_client: connected Telethon TelegramClient (userbot session)
            ai_call: async function `prompt -> response_text`. Plug Claude or Gemini.
            message_window: how many Telegram messages to sample per deal
            rate_limit_sec: gap between deals to respect API limits
        """
        self.amocrm = amocrm
        self.tg_client = tg_client
        self.ai_call = ai_call
        self.message_window = message_window
        self.rate_limit_sec = rate_limit_sec

    async def run(
        self,
        limit: int = 50,
        dry_run: bool = True,
        skip_closed: bool = True,
    ) -> AnalyzerReport:
        report = AnalyzerReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            dry_run=dry_run,
        )

        leads = await self.amocrm.get_leads_detailed(limit=min(max(limit, 1), 250))
        if skip_closed:
            leads = [l for l in leads if l.get("status_id") not in (142, 143)]

        report.checked = len(leads)
        logger.info(f"[DEAL AI] {len(leads)} ta aktiv sdelka tekshiriladi")

        for lead in leads:
            try:
                analysis = await self._analyze_one(lead, dry_run=dry_run)
            except Exception as exc:
                logger.error(f"[DEAL AI] Lead {lead.get('id')} fail: {exc}")
                analysis = DealAnalysis(
                    lead_id=int(lead.get("id") or 0),
                    lead_name=lead.get("name") or "",
                    status="error",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            report.items.append(analysis)
            report.by_category[analysis.category] = (
                report.by_category.get(analysis.category, 0) + 1
            )
            await asyncio.sleep(self.rate_limit_sec)

        logger.info(f"[DEAL AI] Yakun: {report.by_category}")
        return report

    # -----------------------
    # Per-lead pipeline
    # -----------------------

    async def _analyze_one(
        self,
        lead: Dict[str, Any],
        dry_run: bool,
    ) -> DealAnalysis:
        lead_id = int(lead["id"])
        lead_name = lead.get("name") or f"Lead #{lead_id}"
        analysis = DealAnalysis(
            lead_id=lead_id,
            lead_name=lead_name,
            pipeline_id=lead.get("pipeline_id"),
            status_id=lead.get("status_id"),
        )

        identity = await self._gather_identity(lead)
        analysis.telegram_username = identity.get("username")
        analysis.telegram_phone = identity.get("phone")
        analysis.telegram_user_id = identity.get("user_id")

        messages = await self._fetch_telegram_messages(identity)
        analysis.messages_sampled = len(messages)

        prompt = self._build_prompt(lead, identity, messages)
        try:
            raw = await self.ai_call(prompt)
        except Exception as exc:
            raise RuntimeError(f"AI chaqiruv xatosi: {exc}") from exc

        parsed = self._parse_ai_response(raw)
        analysis.category = parsed.get("category", "UNCLEAR")
        analysis.confidence = float(parsed.get("confidence", 0.0) or 0.0)
        analysis.reason = parsed.get("reason", "")
        analysis.evidence = list(parsed.get("evidence", []) or [])[:6]
        analysis.recommended_action = parsed.get("recommended_action", "")

        if dry_run:
            analysis.status = "dry_run"
            return analysis

        tag = CATEGORY_TAGS.get(analysis.category, CATEGORY_TAGS["UNCLEAR"])
        note = self._format_note(analysis)
        tag_ok, note_ok = await self._apply_to_amocrm(lead_id, tag, note)
        analysis.tag_applied = tag if tag_ok else None
        analysis.note_applied = note_ok
        analysis.status = "applied" if (tag_ok and note_ok) else "error"
        return analysis

    # -----------------------
    # Identity & Telegram messages
    # -----------------------

    async def _gather_identity(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        text = lead.get("name") or ""
        phone: Optional[str] = None
        username: Optional[str] = None
        contact_id: Optional[int] = None

        try:
            notes = await self.amocrm.get_lead_notes(int(lead["id"]))
        except Exception:
            notes = []
        notes_text = " ".join(
            str((n.get("params") or {}).get("text") or "") for n in (notes or [])
        )

        contacts_ref = (lead.get("_embedded", {}).get("contacts") or [])
        if contacts_ref:
            contact_id = int(contacts_ref[0].get("id") or 0) or None

        contact_text = ""
        if contact_id:
            contact = await asyncio.to_thread(
                self.amocrm.get_contact_details, contact_id
            ) or {}
            contact_text = json.dumps(contact, ensure_ascii=False)[:5000]
            for field in contact.get("custom_fields_values") or []:
                if field.get("field_code") == "PHONE":
                    for value in field.get("values") or []:
                        digits = re.sub(r"\D+", "", str(value.get("value") or ""))
                        if len(digits) >= 9:
                            phone = digits
                            break

        corpus = "\n".join([text, notes_text, contact_text])
        for match in USERNAME_RE.finditer(corpus):
            candidate = match.group(1).lower()
            if 5 <= len(candidate) <= 32 and candidate not in ("gmail", "outlook"):
                username = candidate
                break
        if not phone:
            for match in PHONE_RE.finditer(corpus):
                digits = re.sub(r"\D+", "", match.group(0))
                if len(digits) >= 9:
                    phone = digits
                    break

        user_id: Optional[int] = None
        if (username or phone) and self.tg_client:
            try:
                from telethon.tl import types  # type: ignore
                target = username or ("+" + phone if phone else None)
                if target:
                    entity = await self.tg_client.get_entity(target)
                    if isinstance(entity, types.User):
                        user_id = int(entity.id)
                        if not username and getattr(entity, "username", None):
                            username = entity.username.lower()
                        if not phone and getattr(entity, "phone", None):
                            phone = re.sub(r"\D+", "", entity.phone)
            except Exception as exc:
                logger.debug(f"[DEAL AI] get_entity skip: {exc}")

        return {
            "phone": phone,
            "username": username,
            "user_id": user_id,
            "contact_id": contact_id,
            "corpus_snippet": corpus[:1200],
        }

    async def _fetch_telegram_messages(self, identity: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.tg_client:
            return []
        target = identity.get("user_id") or identity.get("username")
        if not target and identity.get("phone"):
            target = "+" + identity["phone"]
        if not target:
            return []
        try:
            messages: List[Dict[str, Any]] = []
            async for msg in self.tg_client.iter_messages(target, limit=self.message_window):
                if not msg or not getattr(msg, "text", None):
                    continue
                messages.append(
                    {
                        "date": msg.date.isoformat() if msg.date else None,
                        "out": bool(msg.out),
                        "text": str(msg.text)[:600],
                    }
                )
            messages.reverse()
            return messages
        except Exception as exc:
            logger.debug(f"[DEAL AI] iter_messages skip ({target}): {exc}")
            return []

    # -----------------------
    # Prompt and parsing
    # -----------------------

    def _build_prompt(
        self,
        lead: Dict[str, Any],
        identity: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> str:
        lead_snippet = {
            "id": lead.get("id"),
            "name": lead.get("name"),
            "price": lead.get("price"),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "created_at": lead.get("created_at"),
            "updated_at": lead.get("updated_at"),
            "responsible_user_id": lead.get("responsible_user_id"),
        }

        identity_snippet = {
            "phone": identity.get("phone"),
            "username": identity.get("username"),
            "telegram_user_id": identity.get("user_id"),
        }

        conv_lines = []
        for msg in messages[-self.message_window:]:
            role = "Mijoz" if not msg["out"] else "Biz"
            conv_lines.append(f"[{role}] {msg['text']}")
        conversation = "\n".join(conv_lines) or "(Telegram suhbatdan na'muna yo'q)"

        return (
            ANALYZER_PROMPT
            + "\n\n=== AmoCRM Lead ===\n"
            + json.dumps(lead_snippet, ensure_ascii=False, indent=2)
            + "\n\n=== Identifikator ===\n"
            + json.dumps(identity_snippet, ensure_ascii=False, indent=2)
            + "\n\n=== Telegram suhbat (oxirgi) ===\n"
            + conversation
            + "\n\nJSON javob:"
        )

    @staticmethod
    def _parse_ai_response(raw: str) -> Dict[str, Any]:
        if not raw:
            return {}
        text = raw.strip()
        # Strip code fences if present
        fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        # Extract first JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception as exc:
            logger.warning(f"[DEAL AI] JSON parse failed: {exc}")
            return {}

    # -----------------------
    # AmoCRM annotation
    # -----------------------

    async def _apply_to_amocrm(self, lead_id: int, tag: str, note: str) -> tuple[bool, bool]:
        try:
            tag_ok = bool(await self.amocrm.add_lead_tag(lead_id, tag))
        except Exception as exc:
            logger.warning(f"[DEAL AI] tag fail {lead_id}: {exc}")
            tag_ok = False
        try:
            note_ok = bool(await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, note))
        except Exception as exc:
            logger.warning(f"[DEAL AI] note fail {lead_id}: {exc}")
            note_ok = False
        return tag_ok, note_ok

    def _format_note(self, analysis: DealAnalysis) -> str:
        label = CATEGORY_LABEL_UZ.get(analysis.category, analysis.category)
        evidence = "\n".join(f"- {x}" for x in analysis.evidence[:6]) or "- (dalil yo'q)"
        return (
            "Oisha AI Audit (Sdelka tahlili)\n"
            f"Kategoriya: {label} [{analysis.category}]\n"
            f"Ishonch: {analysis.confidence:.2f}\n"
            f"Sabab: {analysis.reason}\n"
            f"Telegram: @{analysis.telegram_username or '-'} "
            f"({analysis.telegram_phone or 'raqam yo’q'})\n"
            f"Telegram xabarlar tahlilda: {analysis.messages_sampled}\n"
            f"Dalillar:\n{evidence}\n"
            f"Tavsiya: {analysis.recommended_action or '-'}\n"
            "Avtomatik o'chirish qilinmadi. Tegga qarab javob bering."
        )


def report_to_dict(report: AnalyzerReport) -> Dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "checked": report.checked,
        "by_category": report.by_category,
        "dry_run": report.dry_run,
        "items": [asdict(item) for item in report.items],
    }
