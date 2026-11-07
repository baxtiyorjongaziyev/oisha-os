"""Jon CRM — Call Intelligence and Whisper STT Service.

Ushbu modul sotuvchilar va mijozlar suhbatini O'zbek tilida transkripsiya qiladi
(Google Gemini 2.5/2.0 Flash primary, Groq Whisper fallback), suhbatdan BANT
ko'rsatkichlari, mijoz og'riqlari, e'tirozlar va keyingi qadamlarni aniqlaydi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

DB_PATH = "data/crm_dialer.db"


class CallIntelService:
    """Qo'ng'iroqlarni transkripsiya qilish va BANT tahlili xizmati."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._moizvonki_session: Optional[requests.Session] = None

    def _get_conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_moizvonki_session(self) -> Optional[requests.Session]:
        if self._moizvonki_session:
            return self._moizvonki_session
        email = os.getenv("MOIZVONKI_EMAIL")
        password = os.getenv("MOIZVONKI_PASSWORD")
        domain = os.getenv("MOIZVONKI_DOMAIN", "jonbrandingagency.moizvonki.ru").strip()
        if not email or not password:
            return None

        session = requests.Session()
        login_url = f"https://{domain}/accounts/login/"
        try:
            r = session.get(login_url, timeout=15)
            csrf_mid = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', r.text)
            csrf_val = csrf_mid.group(1) if csrf_mid else session.cookies.get("csrftoken")
            data = {"csrfmiddlewaretoken": csrf_val, "username": email, "password": password, "foreign_pc": "on"}
            headers = {"Referer": login_url, "User-Agent": "Mozilla/5.0"}
            r_post = session.post(login_url, data=data, headers=headers, timeout=15)
            if r_post.status_code == 200 and "sessionid" in session.cookies:
                self._moizvonki_session = session
                return session
        except Exception as e:
            logger.warning("[CALL-INTEL] MoiZvonki login failed: %s", e)
        return None

    def download_audio_bytes(self, audio_url: str) -> Optional[Tuple[bytes, str]]:
        """MoiZvonki yoki to'g'ridan-to'g'ri URL orqali audio baytlarini yuklab olish."""
        if not audio_url or not audio_url.startswith("http"):
            return None
        sess = None
        if "moizvonki" in audio_url:
            sess = self._get_moizvonki_session()
        client = sess if sess else requests.Session()
        try:
            resp = client.get(audio_url, timeout=40)
            if resp.status_code == 200 and resp.content and len(resp.content) > 1000:
                # 60027 baytlik soxta login sahifasi audiosini rad etish
                if len(resp.content) == 60027:
                    logger.warning("[CALL-INTEL] MoiZvonki sessiya talab qildi (60027b)")
                    return None
                ctype = resp.headers.get("Content-Type", "audio/mp3").split(";")[0]
                return resp.content, ctype
        except Exception as e:
            logger.error("[CALL-INTEL] Audio yuklab olishda xatolik: %s", e)
        return None

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
        """Audio yozuvni Oʼzbek tilida transkripsiya qilish (faqat Gemini)."""
        prompt = (
            "Siz professional savdo qo'ng'iroqlari bo'yicha transkripsiya mutaxassisisiz. "
            "Ushbu suhbat audiosini diqqat bilan eshiting va to'liq O'zbek tilida (lotin alifbosida) yozing.\n"
            "Format:\n"
            "[00:05] Menejer: ...\n"
            "[00:12] Mijoz: ...\n"
            "Gapiruvchini aniq 'Menejer:' va 'Mijoz:' deb belgilang. Tushunarsiz so'zlarni to'qimang."
        )

        # 1. Google Gemini GenAI SDK orqali
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key and not gemini_key.startswith("sk-place"):
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)
                part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                model_name = os.getenv("GEMINI_CALL_MODEL", "gemini-2.0-flash")
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=[prompt, part],
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=4096),
                )
                text = (getattr(resp, "text", "") or "").strip()
                if text and len(text) > 20:
                    return text
            except Exception as e:
                logger.warning("[CALL-INTEL] Gemini STT xatolik berdi: %s", e)

        return "Suhbat audiosi yuklandi, ammo aniq nutq ajratib olinmadi."

    async def analyze_transcript(
        self, transcript: str, lead: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Transkripsiyani BANT va savdo mezonlari bo'yicha tahlil qilish."""
        if not transcript or len(transcript.strip()) < 15:
            return self._build_default_analysis(lead, "Suhbat transkripsiyasi juda qisqa.")

        client_name = (lead or {}).get("contact_name") or "Mijoz"
        budget = (lead or {}).get("price") or 0

        prompt = f"""Quyidagi sotuv qo'ng'irog'i transkripsiyasini tahlil qiling va O'zbek tilida aniq JSON qaytaring.

MIJOZ KONTEKSTI:
Ism: {client_name}
Taxminiy byudjet: {budget} so'm

TRANSKRIPSIYA:
{transcript}

Talab qilinadigan JSON formati (faqat JSON qaytaring):
{{
  "bant_score": 75,
  "sentiment": "Issiq (Yuqori qiziqish) | Iliq (Saralash kerak) | Sovuq",
  "summary": "2-3 gapda suhbatning qisqa va aniq mazmuni",
  "pain_point": "Mijozning asosiy og'rig'i yoki ehtiyoji",
  "objections": ["E'tiroz 1", "E'tiroz 2"],
  "next_best_action": "Sotuvchi qilishi kerak bo'lgan keyingi aniq harakat",
  "recommendations": [
    "1. Tavsiya...",
    "2. Tavsiya...",
    "3. Tavsiya..."
  ]
}}"""

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from google import genai

                client = genai.Client(api_key=gemini_key)
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                text = (getattr(resp, "text", "") or "").strip()
                cleaned = re.sub(r"^```(?:json)?\s*", "", text)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                data["analyzed_at"] = get_local_now().strftime("%Y-%m-%d %H:%M")
                return data
            except Exception as e:
                logger.warning("[CALL-INTEL] Gemini tahlili xatosi: %s", e)

        # 2. Fallback: Free AI Router (Groq/Cloudflare)
        try:
            from src.services.utils.free_ai_router import get_free_ai_router

            router = get_free_ai_router()
            routed = await router.generate_text(prompt)
            if routed and routed.text:
                cleaned = re.sub(r"^```(?:json)?\s*", "", routed.text.strip())
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                data["analyzed_at"] = get_local_now().strftime("%Y-%m-%d %H:%M")
                return data
        except Exception as e:
            logger.warning("[CALL-INTEL] Free AI Router tahlil xatosi: %s", e)

        return self._build_default_analysis(lead, transcript)

    def _build_default_analysis(
        self, lead: Optional[Dict[str, Any]], transcript: str
    ) -> Dict[str, Any]:
        score = 65
        price = float((lead or {}).get("price") or 0.0)
        if price > 5_000_000:
            score += 15
        return {
            "bant_score": min(score, 90),
            "sentiment": "Iliq (Saralash kerak)",
            "summary": f"Mijoz bilan qo'ng'iroq amalga oshirildi. Suhbat matni: {transcript[:120]}...",
            "pain_point": "Brend identifikatsiyasi va xizmat sifati bo'yicha aniqlik kiritish",
            "objections": ["Narx va muddat bo'yicha muzokara"],
            "next_best_action": "Tijoriy taklif (KP) yuborish va diagnostika uchrashuvi vaqtini belgilash",
            "recommendations": [
                "1. Mijozning byudjet doirasiga mos 3 ta variantli taklif bering.",
                "2. Avvalgi o'xshash loyihalar keysini ko'rsatib ishonch hosil qiling.",
                "3. 24 soat ichida qayta bog'lanib qarorni so'rang.",
            ],
            "analyzed_at": get_local_now().strftime("%Y-%m-%d %H:%M"),
        }

    async def process_lead_call_intelligence(
        self,
        lead_id: int,
        audio_url: Optional[str] = None,
        transcript_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bitim bo'yicha to'liq STT transkripsiya va BANT tahlilini yurgazish va bazaga saqlash."""
        lead = None
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            if row:
                lead = dict(row)

        if not lead:
            return {"success": False, "detail": "Bitim topilmadi"}

        transcript = transcript_override or ""
        target_audio = audio_url or lead.get("last_audio_url") or ""

        # Agar transkripsiya berilmagan bo'lsa, audiodan ajratish
        if not transcript and target_audio:
            audio_data = self.download_audio_bytes(target_audio)
            if audio_data:
                raw_bytes, mtype = audio_data
                transcript = await self.transcribe_audio(raw_bytes, mtype)

        if not transcript:
            transcript = "Audio fayl yuklanmadi yoki ovoz aniqlanmadi."

        # BANT va savdo xulosasini hisoblash
        analysis = await self.analyze_transcript(transcript, lead)

        # Tarix (notes_json) ga yangi suhbat tahlili kartasini biriktirish
        notes: List[Dict[str, Any]] = []
        raw_notes = lead.get("notes_json") or "[]"
        try:
            notes = json.loads(raw_notes) if isinstance(raw_notes, str) else list(raw_notes)
        except Exception:
            notes = []

        now_str = get_local_now().strftime("%H:%M")
        new_intel_note = {
            "id": f"intel_{int(time.time())}",
            "note_type": "call_intel",
            "text": f"✨ [Oisha AI Tahlili]\n{analysis.get('summary')}",
            "by": "Oisha AI STT",
            "time": now_str,
            "transcript": transcript,
            "audio_url": target_audio,
            "ai_analysis": analysis,
        }
        notes.append(new_intel_note)

        # Bazaga saqlash
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE dialer_leads
                SET notes_json = ?, ai_analysis_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(notes, ensure_ascii=False), json.dumps(analysis, ensure_ascii=False), lead_id),
            )
            conn.commit()

        return {
            "success": True,
            "lead_id": lead_id,
            "transcript": transcript,
            "analysis": analysis,
            "audio_url": target_audio,
        }

    async def run_holistic_deal_analysis(self, lead_id: int) -> Dict[str, Any]:
        """Bitimdagi barcha aloqalar va ma'lumotlar asosida 360° AI xulosasi tuzish."""
        lead = None
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            if row:
                lead = dict(row)

        if not lead:
            return {"success": False, "detail": "Bitim topilmadi"}

        notes_raw = lead.get("notes_json") or "[]"
        try:
            notes = json.loads(notes_raw)
        except Exception:
            notes = []

        all_text_parts = [f"Bitim: {lead.get('name')} | Narx: {lead.get('price')} so'm"]
        for n in notes:
            t = n.get("text") or n.get("transcript") or ""
            if t:
                all_text_parts.append(f"[{n.get('time', 'Bugun')} {n.get('by', '')}]: {t}")

        full_context = "\n".join(all_text_parts)
        analysis = await self.analyze_transcript(full_context, lead)

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE dialer_leads SET ai_analysis_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(analysis, ensure_ascii=False), lead_id),
            )
            conn.commit()

        return {"success": True, "lead_id": lead_id, "analysis": analysis}


call_intel_service = CallIntelService()
