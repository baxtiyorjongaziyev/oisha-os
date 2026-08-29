import os
import re
import io
import time
import json
import logging
import asyncio
import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog
import requests as _requests
from src.database import Database
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.stt_service import STTService
from src.services.core.call_events import CallEventLog
from src.services.core.call_analyses_schema import ensure_call_analysis_schema
from src.services.core.sales_playbook import (
    IDEAL_CLIENT_TALK_PCT,
    MAX_ACCEPTABLE_PAUSE_SECONDS,
    OUTCOME_LABELS_UZ,
    OUTCOME_UNKNOWN,
    STAGE_WEIGHTS,
    normalise_outcome,
    outcome_converted,
    outcome_prompt_uz,
    rubric_prompt_uz,
)
from src.services.utils.transcript import (
    detect_pauses,
    format_timestamp,
    has_timestamps,
    speaker_split,
    strip_timestamps,
    talk_ratio_verdict,
)
from src.time_utils import get_local_now, get_local_timezone
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallCrmNotesMixin:
    @staticmethod
    def _score_bar(score: int) -> str:
        """10-block score bar: filled=█, empty=░. E.g. 85/100 → ████████░░ 85/100"""
        filled = round(max(0, min(100, score)) / 10)
        return "█" * filled + "░" * (10 - filled) + f" {score}/100"

    def _build_amocrm_note(
        self,
        analysis: Dict[str, Any],
        transcript_snippet: str = "",
        caller_phone: str = "",
        call_id: str = "",
        duration_seconds: int = 0,
        # legacy keyword args kept for back-compat (ignored, taken from analysis)
        category: str = "",
        summary: str = "",
        client_mood: str = "",
        next_steps: str = "",
        client_talk_pct: int = 0,
        agent_talk_pct: int = 0,
        talk_ratio_verdict: str = "",
    ) -> str:
        """MetaSell Note 1 — Oisha AI tahlil natijasi."""
        _summary = str(analysis.get("summary") or summary or "").strip()
        _category = str(analysis.get("category") or category or "Boshqa")
        _mood = str(analysis.get("client_mood") or client_mood or "Noaniq")
        _next = str(analysis.get("next_steps") or next_steps or "N/A").strip() or "N/A"
        _client_pct = int(analysis.get("client_talk_pct") or client_talk_pct or 0)
        _agent_pct = int(analysis.get("agent_talk_pct") or agent_talk_pct or 0)
        _talk_verdict = str(analysis.get("talk_ratio_verdict") or talk_ratio_verdict or "")
        sifat = int(analysis.get("sifat_bahosi") or 0)
        lead_b = int(analysis.get("lead_bahosi") or 0)
        suhbat_oilasi = str(analysis.get("suhbat_oilasi") or "Boshqa")
        suhbat_domeni = str(analysis.get("suhbat_domeni") or "Boshqa")
        baholash = str(analysis.get("baholash_rejimi") or "Savdo playbook boyicha baholanadi")
        mosligi = str(analysis.get("biznes_mosligi") or "Noaniq")
        servis = str(analysis.get("servis_yonalishi") or "Boshqa")

        rubrik = analysis.get("rubrik_baholar") or {}
        r_salom = int(rubrik.get("salomlashish") or 0)
        r_ehti = int(rubrik.get("ehtiyojlar") or 0)
        r_qiy = int(rubrik.get("qiymat") or 0)
        r_etir = int(rubrik.get("etirozlar") or 0)
        r_yak = int(rubrik.get("yakunlash") or 0)
        r_mul = int(rubrik.get("muloqot_sifati") or 0)

        rubrik_amal_qiladi = bool(analysis.get("rubrik_amal_qiladi", True))
        attributed = bool(analysis.get("talk_ratio_attributed", True))

        lines = [
            f"[{ANALYSIS_MARKER}] Oisha AI tahlil natijasi",
            "",
            _summary,
            "",
        ]

        if rubrik_amal_qiladi:
            lines += [
                f"Sifat bahosi:  {self._score_bar(sifat)}",
                f"Lead bahosi:   {self._score_bar(lead_b)}",
            ]
        else:
            lines.append("Baholanmadi — savdo suhbati emas yoki suhbat juda qisqa")

        lines += [
            f"Suhbat oilasi: {suhbat_oilasi}",
            f"Suhbat domeni: {suhbat_domeni}",
            f"Baholash rejimi: {baholash}",
            f"Biznes mosligi: {mosligi}",
            f"Servis yo'nalishi: {servis}",
            f"Kayfiyat: {_mood}",
        ]

        if rubrik_amal_qiladi:
            lines += [
                "",
                "──── JON BRANDING RUBRIK (6 bosqich) ────",
                f"1. Salomlashish:    {self._score_bar(r_salom)}",
                f"2. Ehtiyojlar:      {self._score_bar(r_ehti)}",
                f"3. Qiymat:          {self._score_bar(r_qiy)}",
                f"4. E'tirozlar (×2): {self._score_bar(r_etir)}",
                f"5. Yakunlash  (×2): {self._score_bar(r_yak)}",
                f"6. Muloqot sifati:  {self._score_bar(r_mul)}",
            ]

        if rubrik_amal_qiladi:
            outcome = normalise_outcome(analysis.get("natija"))
            lines += [
                "",
                f"Natija: {OUTCOME_LABELS_UZ.get(outcome, 'Aniqlanmadi')}"
                + ("  ✅ konversiya" if outcome_converted(outcome) else ""),
            ]

            breakdown_at = analysis.get("uzilish_vaqti")
            breakdown_reason = str(analysis.get("uzilish_sababi") or "").strip()
            if breakdown_at:
                lines += [
                    "",
                    f"🔴 MIJOZ YO'QOLGAN LAHZA: {breakdown_at}"
                    + (f" — {breakdown_reason}" if breakdown_reason else ""),
                ]

            pauses = analysis.get("pauzalar") or []
            if pauses:
                longest = max(pauses, key=lambda p: p.get("davomiyligi", 0))
                lines.append(
                    f"⏸ Keraksiz pauza: {len(pauses)} ta "
                    f"(eng uzuni {longest.get('vaqt')} da "
                    f"{longest.get('davomiyligi')}s)"
                )

            kuchli = [str(x) for x in (analysis.get("kuchli_tomonlar") or [])]
            zaif = [str(x) for x in (analysis.get("zaif_tomonlar") or [])]
            if kuchli or zaif:
                lines.append("")
                lines.append("──── MURABBIY IZOHI ────")
                for item in kuchli[:3]:
                    lines.append(f"✅ {item}")
                for item in zaif[:3]:
                    lines.append(f"⚠️ {item}")

        lines += [
            "",
            f"Keyingi qadam: {_next}",
        ]
        if attributed:
            lines.append(
                f"Gapirish nisbati: Mijoz {_client_pct}% | Sotuvchi {_agent_pct}%"
            )
        elif _client_pct or _agent_pct:
            lines.append(
                f"So'zlovchilar nisbati: {_client_pct}% / {_agent_pct}% "
                "(rollar noma'lum)"
            )
        if _talk_verdict:
            lines.append(_talk_verdict)

        if transcript_snippet:
            snippet = _clip(transcript_snippet, self.max_transcript_note_chars)
            lines += ["", "Transkripsiya (O'zbek):", snippet]

        return "\n".join(lines).strip()

    def _build_client_profile_note(
        self,
        analysis: Dict[str, Any],
        phone: str = "",
        call_id: str = "",
        duration_seconds: int = 0,
    ) -> str:
        """MetaSell Note 2 — Oisha AI: Mijoz profili."""
        lavozim = str(analysis.get("mijoz_lavozimi") or "N/A")
        kompaniya = str(analysis.get("mijoz_kompaniya") or "N/A")
        qaror = str(analysis.get("qaror_qabul_qiluvchi") or "Noaniq")
        joylashuv = str(analysis.get("joylashuv") or "N/A")
        malumotlar = analysis.get("mijoz_malumotlari") or []
        if isinstance(malumotlar, str):
            malumotlar = [malumotlar]

        lines = [
            f"[{ANALYSIS_MARKER}] Oisha AI: Mijoz profili",
            "",
            f"Lavozimi: {lavozim}",
            f"Kompaniya: {kompaniya}",
            f"Qaror qabul qiluvchi: {qaror}",
            f"Joylashuv: {joylashuv}",
        ]
        if malumotlar:
            lines.append("")
            lines.append("Ma'lumotlar:")
            for item in malumotlar[:10]:
                lines.append(f"• {item}")

        meta_parts = []
        if phone:
            meta_parts.append(f"Qo'ng'iroq: {phone}")
        if duration_seconds:
            meta_parts.append(f"Davomiylik: {duration_seconds}s")
        if call_id:
            meta_parts.append(f"ID: {call_id}")
        if meta_parts:
            lines.append("")
            lines.append(" | ".join(meta_parts))

        return "\n".join(lines).strip()
