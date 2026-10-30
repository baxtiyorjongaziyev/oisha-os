"""Automatically version private script examples from CRM-confirmed won leads."""
from __future__ import annotations

import asyncio
import logging
import inspect
import time
from pathlib import Path
from typing import Any

from src.services.call_analytics.script_evidence import (
    extract_examples, quality_score, script_group, verified_sale,
)
from src.services.call_analytics.script_library import DEFAULT_LIBRARY, ScriptLibrary

logger = logging.getLogger(__name__)


class WinningScriptEvolver:
    def __init__(self, db: Any = None, tg_client: Any = None, *, path: Path | None = None):
        self.db = db
        self.tg_client = tg_client
        self.library = ScriptLibrary(DEFAULT_LIBRARY if path is None else path)

    def is_winning_call(self, analysis: dict) -> bool:
        """High quality is a candidate filter, never proof of a won sale."""
        return quality_score(analysis) is not None and script_group(analysis) is not None

    async def evolve_from_call(
        self, lead_id: int, caller_phone: str, manager_name: str,
        duration_seconds: int, transcript: str, analysis: dict,
        *, call_id: str = "", occurred_at: int = 0,
    ) -> dict | None:
        if not self.is_winning_call(analysis) or not call_id:
            return None
        if not isinstance(occurred_at, int) or not 0 < occurred_at <= int(time.time()):
            return None
        examples = extract_examples(transcript)
        if not examples:
            return None
        sample = {
            "call_id": call_id, "lead_id": lead_id, "occurred_at": occurred_at,
            "group_key": script_group(analysis), "score": quality_score(analysis),
            "examples": examples,
        }
        inserted = await asyncio.to_thread(self.library.capture, sample)
        return {"call_id": call_id, "state": "pending_crm_verification"} if inserted else None

    async def reconcile(self, amocrm: Any, limit: int = 20, min_interval: int = 0) -> dict:
        """Revisit captured calls after deals close, including analyzed calls."""
        now = int(time.time())
        checked = errors = 0
        for lead_id in await asyncio.to_thread(self.library.next_leads, limit, now - min_interval):
            try:
                getter = amocrm.get_lead
                if asyncio.iscoroutinefunction(getter):
                    lead = await getter(lead_id)
                else:
                    lead = await asyncio.to_thread(getter, lead_id)
                    if inspect.isawaitable(lead):
                        lead = await lead
                if not isinstance(lead, dict) or lead.get("id") != lead_id:
                    raise ValueError("invalid_crm_response")
                for sample in await asyncio.to_thread(self.library.samples_for_lead, lead_id):
                    won = verified_sale(lead, lead_id, sample["occurred_at"], now)
                    await asyncio.to_thread(self.library.verify, sample["call_id"], won, now)
                checked += 1
            except Exception as exc:
                errors += 1
                logger.warning("[SCRIPT LEARNING] CRM verification failed: %s", type(exc).__name__)
            finally:
                await asyncio.to_thread(self.library.mark_attempt, lead_id, now)
        versions = await asyncio.to_thread(self.library.rebuild, now)
        return {"checked_leads": checked, "errors": errors, "updated_scripts": versions}

    def current_scripts(self) -> list[dict]:
        return self.library.current()

    def format_current_scripts(self) -> str | None:
        scripts = self.current_scripts()
        if not scripts:
            return None
        lines = ["SOTUV NAMUNALARIDAN YANGILANGAN SKRIPTLAR",
                 "CRM yutilgan bitimlar; pul tushgani tasdiqlanmagan. Iboralarni vaziyatga moslang."]
        for script in scripts:
            lines.append(f"\n{script['group']} — v{script['version']}")
            for example in script["examples"][:3]:
                lines.append(f"Manba: lead #{example['lead_id']}, call {example['call_id']}")
                lines.extend(f"• {phrase}" for phrase in example["phrases"][:2])
        return "\n".join(lines)
