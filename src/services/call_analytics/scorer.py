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

class CallScorerMixin:
    async def analyze_transcript(
        self, transcript: str, duration_seconds: int = 0
    ) -> Dict[str, Any]:
        """Classify, summarize, and extract next steps from a transcript."""
        if not transcript:
            return self._fallback_analysis(transcript)

        try:
            from google.genai import types

            client_pct, agent_pct, attributed = _speaker_split(transcript)
            ratio_line = (
                f"  Mijoz: {client_pct}%  |  Sotuvchi: {agent_pct}%\n"
                if attributed
                else "  Aniqlanmadi — transkripsiyada rollar belgilanmagan.\n"
            )
            now_local = get_local_now()
            prompt = (
                "Quyidagi telefon suhbati transkripsiyasini professional savdo tahlilchisi sifatida tahlil qiling.\n\n"
                f"HOZIRGI SANA VA VAQT (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')} "
                f"({_WEEKDAY_UZ[now_local.weekday()]})\n"
                "Transkripsiyada nisbiy vaqt aytilsa (\"ertaga\", \"peshin\", \"kelasi hafta\", "
                "\"dushanba\"), shu hozirgi sanaga nisbatan hisoblang.\n\n"
                "TOIFALAR (faqat bittasini tanlang):\n"
                "- Shaxsiy: shaxsiy, biznesga aloqasi yo'q suhbat.\n"
                "- Oila: oila a'zolari, uy ishlari, bolalar yoki qarindoshlar haqida.\n"
                "- Jamoa: xodimlar, ichki ishlar, vazifa, deadline, operatsion muhokama.\n"
                "- Mijoz: brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n"
                "- Boshqa: aralash, spam yoki yuqoridagilarga aniq kirmaydigan qo'ng'iroq.\n\n"
                "GAPIRISH NISBATI (hisoblangan):\n"
                f"{ratio_line}"
                f"  Ideal: mijoz ≥{IDEAL_CLIENT_TALK_PCT}%.\n\n"
                f"{rubric_prompt_uz()}\n"
                f"{outcome_prompt_uz()}\n"
                "Rubrik faqat Mijoz toifasiga taalluqli. Agar toifa Mijoz emas "
                "(Shaxsiy, Oila, Jamoa, Boshqa) bo'lsa — rubrik_baholar uchun "
                "umumiy muloqot sifatiga qarab baholang.\n\n"
                "Javobni faqat JSON formatida qaytaring:\n"
                "{\n"
                '  "summary": "2-4 gapda O\'zbekcha xulosa",\n'
                '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
                '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
                '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
                '  "kelishilgan_vaqt": "Agar suhbatda aniq kun/soat kelishilgan bo\'lsa '
                '(masalan \'ertaga soat 15da\', \'dushanba peshin\'), uni YYYY-MM-DD HH:MM '
                'formatida yozing (hozirgi sanaga nisbatan hisoblab). Aniq vaqt aytilmagan '
                'bo\'lsa — null.",\n'
                f'  "client_talk_pct": {client_pct},\n'
                f'  "agent_talk_pct": {agent_pct},\n'
                '  "lead_bahosi": <0-100: lead potensiali — qiziqish, byudjet, qaror qabul qilish>,\n'
                '  "suhbat_oilasi": "Ehtiyoj aniqlash|Yechim taqdimoti|Narx muhokamasi|Follow-up|Shartnoma|Boshqa",\n'
                '  "suhbat_domeni": "Savdo|Mijoz xizmati|Loyiha muhokamasi|Texnik|Boshqa",\n'
                '  "baholash_rejimi": "Savdo playbook boyicha baholanadi|Xizmat standarti|Loyiha boshqaruvi|Boshqa",\n'
                '  "biznes_mosligi": "Biznesga mos|Qisman mos|Mos emas",\n'
                '  "servis_yonalishi": "Brending|Dizayn|SMM|Sayt|Biznes transformatsiya|Reklama|Boshqa",\n'
                '  "mijoz_lavozimi": "lavozim yoki N/A",\n'
                '  "mijoz_kompaniya": "kompaniya nomi yoki N/A",\n'
                '  "qaror_qabul_qiluvchi": "Ha|Yoq|Noaniq",\n'
                '  "joylashuv": "shahar/viloyat yoki N/A",\n'
                '  "mijoz_malumotlari": ["mijoz haqida muhim ma\'lumot 1", "muhim ma\'lumot 2"],\n'
                '  "natija": "yuqoridagi natija kalitlaridan bittasi",\n'
                '  "uzilish_vaqti": "Agar suhbat biror lahzada BUZILGAN bo\'lsa '
                '(mijoz qiziqishdan qolgan, e\'tiroz javobsiz qolgan, savdo uzilgan) '
                '— o\'sha gapning vaqt belgisini \"mm:ss\" formatida yozing. '
                'Suhbat yaxshi ketgan yoki lahzani aniqlab bo\'lmasa — null.",\n'
                '  "uzilish_sababi": "Uzilish lahzasida AYNAN nima noto\'g\'ri ketdi '
                '(masalan: \"Ehtiyoj aniqlanmadi\", \"E\'tirozga javob berilmadi\"). '
                'uzilish_vaqti null bo\'lsa — null.",\n'
                '  "kuchli_tomonlar": ["menejer aynan nimani YAXSHI qildi (1-3 ta, aniq)"],\n'
                '  "zaif_tomonlar": ["menejer nimani o\'tkazib yubordi yoki xato qildi '
                '(1-3 ta, aniq va tuzatib bo\'ladigan)"],\n'
                '  "etirozlar": ["mijoz bildirgan e\'tirozlar, masalan \'qimmat\'"],\n'
                '  "rubrik_baholar": {\n'
                '    "salomlashish": {"ball": <0-100>},\n'
                '    "ehtiyojlar": {"ball": <0-100>},\n'
                '    "qiymat": {"ball": <0-100>},\n'
                '    "etirozlar": {"ball": <0-100>},\n'
                '    "yakunlash": {"ball": <0-100>},\n'
                '    "muloqot_sifati": {"ball": <0-100>}\n'
                '  }\n'
                "}\n\n"
                f"Transkripsiya:\n{transcript}"
            )
            response = await self._gemini_generate_content(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = _extract_json_object(getattr(response, "text", "") or "")
            return self._normalise_analysis(data, transcript, duration_seconds)
        except GeminiQuotaCooldownError:
            logger.info("[CALL] Gemini transcript analysis skipped during quota cooldown.")
            fallback_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds
            )
            if not fallback_analysis:
                fallback_analysis = await self._analyze_transcript_free_ai(
                    transcript, duration_seconds
                )
            if fallback_analysis:
                return fallback_analysis
            return self._fallback_analysis(transcript)
        except Exception as exc:
            logger.error("[CALL] Transcript analysis failed: %s", exc)
            fallback_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds
            )
            if not fallback_analysis:
                fallback_analysis = await self._analyze_transcript_free_ai(
                    transcript, duration_seconds
                )
            if fallback_analysis:
                return fallback_analysis
            return self._fallback_analysis(transcript)

    async def _analyze_transcript_openai(
        self, transcript: str, duration_seconds: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via OpenAI text model."""
        if not self.openai_client:
            return None

        model = getattr(self._settings, "OPENAI_TEXT_MODEL", "gpt-4o-mini")
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq tahlilchisisiz. "
            "Faqat JSON qaytaring."
        )
        now_local = get_local_now()
        user = (
            "Telefon suhbati transkripsiyasini tahlil qiling.\n"
            f"Hozirgi sana va vaqt (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')}\n"
            "Toifalar: Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Kayfiyat: Ijobiy, Neytral, Salbiy, Noaniq.\n"
            "JSON schema: summary, category, client_mood, next_steps, "
            "kelishilgan_vaqt (suhbatda aniq kun/soat kelishilgan bo'lsa "
            "\"YYYY-MM-DD HH:MM\" formatida, aks holda null).\n\n"
            f"Transkripsiya:\n{transcript}"
        )

        def _create():
            return self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

        try:
            response = await asyncio.to_thread(_create)
            raw = response.choices[0].message.content if response.choices else ""
            data = _extract_json_object(raw or "")
            return self._normalise_analysis(data, transcript, duration_seconds)
        except Exception as exc:
            logger.error("[CALL] OpenAI analysis fallback failed: %s", exc)
            return None

    async def _analyze_transcript_free_ai(
        self, transcript: str, duration_seconds: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via free_ai_router (Groq/Cloudflare text models).

        Mirrors the Gemini rubric schema (not the slimmer OpenAI fallback one)
        so MetaSell scoring/conversion diagnostics keep working during a
        Gemini cooldown instead of silently landing at overall_score=0.
        """
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq tahlilchisisiz. "
            "Faqat JSON qaytaring, boshqa matn yozmang."
        )
        now_local = get_local_now()
        prompt = (
            "Quyidagi telefon suhbati transkripsiyasini professional savdo tahlilchisi sifatida tahlil qiling.\n\n"
            f"HOZIRGI SANA VA VAQT (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')}\n\n"
            "TOIFALAR (faqat bittasini tanlang): Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Mijoz = brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n\n"
            f"{rubric_prompt_uz()}\n"
            f"{outcome_prompt_uz()}\n"
            "Rubrik faqat Mijoz toifasiga taalluqli. Boshqa toifalarda "
            "rubrik_baholar uchun umumiy muloqot sifatiga qarab baholang.\n\n"
            "Javobni faqat JSON formatida qaytaring:\n"
            "{\n"
            '  "summary": "2-4 gapda O\'zbekcha xulosa",\n'
            '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
            '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
            '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
            '  "kelishilgan_vaqt": "Aniq kun/soat kelishilgan bo\'lsa YYYY-MM-DD HH:MM, aks holda null",\n'
            '  "natija": "yuqoridagi natija kalitlaridan bittasi",\n'
            '  "kuchli_tomonlar": ["menejer aynan nimani YAXSHI qildi (1-3 ta)"],\n'
            '  "zaif_tomonlar": ["menejer nimani o\'tkazib yubordi (1-3 ta)"],\n'
            '  "etirozlar": ["mijoz bildirgan e\'tirozlar"],\n'
            '  "rubrik_baholar": {\n'
            '    "salomlashish": {"ball": <0-100>},\n'
            '    "ehtiyojlar": {"ball": <0-100>},\n'
            '    "qiymat": {"ball": <0-100>},\n'
            '    "etirozlar": {"ball": <0-100>},\n'
            '    "yakunlash": {"ball": <0-100>},\n'
            '    "muloqot_sifati": {"ball": <0-100>}\n'
            "  }\n"
            "}\n\n"
            f"Transkripsiya:\n{transcript}"
        )
        try:
            # Groq's current default text models (e.g. openai/gpt-oss-120b)
            # are reasoning models: a chunk of max_tokens is consumed by an
            # internal "reasoning" field before any JSON lands in `content`.
            # Too low a budget truncates before the real answer appears, but
            # too high one burns through Groq's 8000 TPM free-tier limit in
            # a single call and forces a 900s _pause() — 1800 is the
            # observed sweet spot for this prompt's reasoning length.
            result = await self.free_ai_router.generate_text(
                prompt, system=system, max_tokens=1800, temperature=0.2
            )
            data = _extract_json_object(result.text if result else "")
            if not data:
                return None
            return self._normalise_analysis(data, transcript, duration_seconds)
        except Exception as exc:
            logger.error("[CALL] free_ai_router analysis fallback failed: %s", exc)
            return None
