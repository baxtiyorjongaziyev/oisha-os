"""
Deal AI Analyzer orchestrator.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List

from src.services.core.deal_ai.identity import fetch_telegram_messages, gather_identity
from src.services.core.deal_ai.models import (
    ANALYZER_PROMPT,
    CATEGORY_LABEL_UZ,
    CATEGORY_TAGS,
    AnalyzerReport,
    DealAnalysis,
)

logger = logging.getLogger(__name__)


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

        identity = await gather_identity(self.amocrm, self.tg_client, lead)
        analysis.telegram_username = identity.get("username")
        analysis.telegram_phone = identity.get("phone")
        analysis.telegram_user_id = identity.get("user_id")

        messages = await fetch_telegram_messages(
            self.tg_client, identity, message_window=self.message_window
        )
        analysis.messages_sampled = len(messages)

        prompt = self._build_prompt(lead, identity, messages)
        try:
            raw = await self.ai_call(prompt)
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
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
        fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception as exc:
            logger.warning(f"[DEAL AI] JSON parse failed: {exc}")
            return {}

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
