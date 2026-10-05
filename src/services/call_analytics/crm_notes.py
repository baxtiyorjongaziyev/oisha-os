from typing import Any, Dict
import structlog
from src.services.core.sales_playbook import (
    OUTCOME_LABELS_UZ,
    normalise_outcome,
    outcome_converted,
)
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallCrmNotesMixin:
    @staticmethod
    def _score_bar(score: int) -> str:
        """10-block score bar: filled=█, empty=░. E.g. 85/100 → ████████░░ 85/100"""
        filled = round(max(0, min(100, score)) / 10)
        return "█" * filled + "░" * (10 - filled) + f" {score}/100"

    _RUBRIC_ROWS = (
        ("1. Salomlashish:    ", "salomlashish"),
        ("2. Ehtiyojlar:      ", "ehtiyojlar"),
        ("3. Qiymat:          ", "qiymat"),
        ("4. E'tirozlar (×2): ", "etirozlar"),
        ("5. Yakunlash  (×2): ", "yakunlash"),
        ("6. Muloqot sifati:  ", "muloqot_sifati"),
    )

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
        _mood = str(analysis.get("client_mood") or client_mood or "Noaniq")
        rubrik_amal_qiladi = bool(analysis.get("rubrik_amal_qiladi", True))

        lines = [
            f"[{ANALYSIS_MARKER}] Oisha AI 360° tahlil natijasi",
            "",
            _summary,
            "",
        ]
        omni = analysis.get("omnichannel_context")
        if omni and hasattr(omni, "format_crm_note_block"):
            lines.append(omni.format_crm_note_block())
            lines.append("")

        lines += self._note_score_lines(analysis, rubrik_amal_qiladi, _mood)
        if rubrik_amal_qiladi:
            lines += self._note_outcome_lines(analysis)
            lines += self._note_coaching_lines(analysis)
        lines += self._note_footer_lines(
            analysis, next_steps, client_talk_pct, agent_talk_pct, talk_ratio_verdict,
        )
        if transcript_snippet:
            snippet = _clip(transcript_snippet, self.max_transcript_note_chars)
            lines += ["", "Transkripsiya (O'zbek):", snippet]

        return "\n".join(lines).strip()

    def _note_score_lines(self, analysis: Dict[str, Any], rubrik_amal_qiladi: bool, mood: str) -> list:
        if rubrik_amal_qiladi:
            lines = [
                f"Sifat bahosi:  {self._score_bar(int(analysis.get('sifat_bahosi') or 0))}",
                f"Lead bahosi:   {self._score_bar(int(analysis.get('lead_bahosi') or 0))}",
            ]
        else:
            lines = ["Baholanmadi — savdo suhbati emas yoki suhbat juda qisqa"]

        lines += [
            f"Suhbat oilasi: {analysis.get('suhbat_oilasi') or 'Boshqa'}",
            f"Suhbat domeni: {analysis.get('suhbat_domeni') or 'Boshqa'}",
            f"Baholash rejimi: {analysis.get('baholash_rejimi') or 'Savdo playbook boyicha baholanadi'}",
            f"Biznes mosligi: {analysis.get('biznes_mosligi') or 'Noaniq'}",
            f"Servis yo'nalishi: {analysis.get('servis_yonalishi') or 'Boshqa'}",
            f"Kayfiyat: {mood}",
        ]

        if rubrik_amal_qiladi:
            rubrik = analysis.get("rubrik_baholar") or {}
            lines += ["", "──── JON BRANDING RUBRIK (6 bosqich) ────"]
            lines += [
                f"{label}{self._score_bar(int(rubrik.get(key) or 0))}"
                for label, key in self._RUBRIC_ROWS
            ]
        return lines

    @staticmethod
    def _note_outcome_lines(analysis: Dict[str, Any]) -> list:
        outcome = normalise_outcome(analysis.get("natija"))
        lines = [
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
        return lines

    @staticmethod
    def _note_coaching_lines(analysis: Dict[str, Any]) -> list:
        kuchli = [str(x) for x in (analysis.get("kuchli_tomonlar") or [])]
        zaif = [str(x) for x in (analysis.get("zaif_tomonlar") or [])]
        tavsiyalar = [str(x) for x in (analysis.get("konversiya_tavsiyalari") or analysis.get("tavsiyalar") or [])]
        if not (kuchli or zaif or tavsiyalar):
            return []
        lines = ["", "──── MURABBIY IZOHI VA KONVERSIYA ────"]
        lines += [f"✅ {item}" for item in kuchli[:3]]
        lines += [f"⚠️ {item}" for item in zaif[:3]]
        lines += [f"💡 Tavsiya: {item}" for item in tavsiyalar[:3]]
        return lines

    @staticmethod
    def _note_footer_lines(
        analysis: Dict[str, Any],
        next_steps: str,
        client_talk_pct: int,
        agent_talk_pct: int,
        talk_ratio_verdict: str,
    ) -> list:
        _next = str(analysis.get("next_steps") or next_steps or "N/A").strip() or "N/A"
        _client_pct = int(analysis.get("client_talk_pct") or client_talk_pct or 0)
        _agent_pct = int(analysis.get("agent_talk_pct") or agent_talk_pct or 0)
        _talk_verdict = str(analysis.get("talk_ratio_verdict") or talk_ratio_verdict or "")

        lines = []
        agreed_dt = analysis.get("kelishilgan_vaqt")
        if agreed_dt and hasattr(agreed_dt, "strftime"):
            lines.append(f"⏰ Kelishilgan vaqt: {agreed_dt.strftime('%d.%m.%Y %H:%M')}")

        lines += ["", f"Keyingi qadam: {_next}"]
        if bool(analysis.get("talk_ratio_attributed", True)):
            lines.append(f"Gapirish nisbati: Mijoz {_client_pct}% | Sotuvchi {_agent_pct}%")
        elif _client_pct or _agent_pct:
            lines.append(
                f"So'zlovchilar nisbati: {_client_pct}% / {_agent_pct}% "
                "(rollar noma'lum)"
            )
        if _talk_verdict:
            lines.append(_talk_verdict)
        return lines

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
