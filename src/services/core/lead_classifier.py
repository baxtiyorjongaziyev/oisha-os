"""
Lead Classifier — AmoCRM sdelkalarni AI orqali klassifikatsiya qilish.
Audio va yozishmalarni tahlil qilib, real mijoz / shaxsiy / spam ekanini aniqlaydi.
"""

import logging
import os
import tempfile
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from google import genai

from src.settings import settings
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger(__name__)


class LeadCategory(str, Enum):
    REAL_CLIENT = "real_client"
    PERSONAL = "personal"
    SPAM = "spam"
    UNCLEAR = "unclear"


@dataclass
class ClassificationResult:
    lead_id: int
    lead_name: str
    category: LeadCategory
    confidence: float
    reason: str
    evidence: List[str] = field(default_factory=list)
    notes_analyzed: int = 0
    audio_transcribed: int = 0
    classified_at: str = field(default_factory=lambda: datetime.now().isoformat())


CLASSIFICATION_PROMPT = """Sen AmoCRM sdelka tahlilchisisiz. Quyidagi sdelka ma'lumotlarini tahlil qilib,
bu sdelka qaysi kategoriyaga tegishli ekanini aniqla:

KATEGORIYALAR:
1. "real_client" — Haqiqiy mijoz: Jon Branding xizmatlariga qiziqish, brending/dizayn/marketing haqida so'rov, narx so'rash, buyurtma berish
2. "personal" — Shaxsiy yozishma: do'stlar/oila bilan suhbat, biznesga aloqasi yo'q, ichki jamoa muloqoti
3. "spam" — Spam/bot: reklama, taklifnomalar, bot xabarlar, ma'nosiz kontakt, noto'g'ri raqam
4. "unclear" — Noaniq: ma'lumot yetarli emas aniqlash uchun

SDELKA MA'LUMOTLARI:
- Nomi: {lead_name}
- Narxi: {price}
- Pipeline: {pipeline}
- Status: {status}
- Mas'ul: {responsible}
- Yaratilgan: {created_at}
- Oxirgi yangilangan: {updated_at}

IZOHLAR VA YOZISHMALAR:
{notes_text}

AUDIO TRANSKRIPTSIYALARI:
{audio_text}

JSON formatida javob ber:
{{
    "category": "real_client" | "personal" | "spam" | "unclear",
    "confidence": 0.0-1.0,
    "reason": "Qisqa sabab (1-2 gap)",
    "evidence": ["dalil 1", "dalil 2"]
}}

Faqat JSON qaytar, boshqa hech narsa yo'q."""


class LeadClassifier:
    """AmoCRM sdelkalarni AI orqali klassifikatsiya qilish."""

    def __init__(self, amocrm: AmoCRMSync, gemini_api_key: str):
        self.amocrm = amocrm
        self.client = genai.Client(api_key=gemini_api_key)
        self.model = os.getenv("GEMINI_LEAD_CLASSIFIER_MODEL", settings.GEMINI_CALL_MODEL)
        self.results: List[ClassificationResult] = []

    async def classify_all_active_leads(self) -> List[ClassificationResult]:
        """Barcha aktiv sdelkalarni klassifikatsiya qilish."""
        logger.info("[CLASSIFIER] Barcha aktiv sdelkalarni tahlil boshlandi...")
        leads = await self.amocrm.get_leads_detailed(limit=50)
        results = []

        for lead in leads:
            if lead.get("status_id") in [142, 143]:
                continue

            result = await self.classify_lead(lead)
            if result:
                results.append(result)

        self.results = results
        logger.info(
            f"[CLASSIFIER] {len(results)} ta sdelka tahlil qilindi: "
            f"real={sum(1 for r in results if r.category == LeadCategory.REAL_CLIENT)}, "
            f"personal={sum(1 for r in results if r.category == LeadCategory.PERSONAL)}, "
            f"spam={sum(1 for r in results if r.category == LeadCategory.SPAM)}"
        )
        return results

    async def classify_lead(self, lead: Dict[str, Any]) -> Optional[ClassificationResult]:
        """Bitta sdelkani klassifikatsiya qilish."""
        lead_id = lead["id"]
        lead_name = lead.get("name", "Nomsiz")

        try:
            notes = await self.amocrm.get_lead_notes(lead_id)
            notes_text, audio_count = self._extract_notes_content(notes)
            audio_text = await self._process_audio_notes(notes, lead_id)

            prompt = CLASSIFICATION_PROMPT.format(
                lead_name=lead_name,
                price=lead.get("price", 0),
                pipeline=lead.get("pipeline_id", "?"),
                status=lead.get("status_id", "?"),
                responsible=lead.get("responsible_user_id", "?"),
                created_at=datetime.fromtimestamp(lead.get("created_at", 0)).strftime("%Y-%m-%d"),
                updated_at=datetime.fromtimestamp(lead.get("updated_at", 0)).strftime("%Y-%m-%d"),
                notes_text=notes_text if notes_text else "(Izohlar yo'q)",
                audio_text=audio_text if audio_text else "(Audio yo'q)",
            )

            response = await self.client.aio.models.generate_content(
                model=self.model, contents=[prompt]
            )

            if not response.text:
                return None

            classification = self._parse_response(response.text)

            return ClassificationResult(
                lead_id=lead_id,
                lead_name=lead_name,
                category=LeadCategory(classification["category"]),
                confidence=classification["confidence"],
                reason=classification["reason"],
                evidence=classification.get("evidence", []),
                notes_analyzed=len(notes),
                audio_transcribed=audio_count,
            )

        except Exception as e:
            logger.error(f"[CLASSIFIER] Lead {lead_id} tahlil xatosi: {e}")
            return None

    def _extract_notes_content(self, notes: List[Dict]) -> tuple:
        """Noteslardan matn kontentini ajratib olish."""
        text_parts = []
        audio_count = 0

        for note in notes:
            note_type = note.get("note_type", "")
            params = note.get("params", {})

            if note_type == "common":
                text = params.get("text", "")
                if text:
                    text_parts.append(f"- {text[:500]}")
            elif note_type in ("voice_message", "file"):
                audio_count += 1
            elif note_type == "call_in" or note_type == "call_out":
                duration = params.get("duration", 0)
                link = params.get("link", "")
                text_parts.append(f"- [Qo'ng'iroq: {duration}s] {link}")
                if link:
                    audio_count += 1
            elif note_type == "sms_in" or note_type == "sms_out":
                text = params.get("text", "")
                if text:
                    text_parts.append(f"- [SMS] {text[:200]}")

        return "\n".join(text_parts[-20:]), audio_count

    async def _process_audio_notes(self, notes: List[Dict], lead_id: int) -> str:
        """Audio noteslarni transkripsiya qilish."""
        transcripts = []

        for note in notes:
            note_type = note.get("note_type", "")
            params = note.get("params", {})

            audio_url = None
            if note_type in ("call_in", "call_out"):
                audio_url = params.get("link")
            elif note_type == "voice_message":
                audio_url = params.get("link") or params.get("file_url")

            if not audio_url:
                continue

            transcript = await self._transcribe_from_url(audio_url)
            if transcript:
                transcripts.append(f"- [Audio] {transcript[:500]}")

            if len(transcripts) >= 5:
                break

        return "\n".join(transcripts)

    async def _transcribe_from_url(self, audio_url: str) -> Optional[str]:
        """Audio URL dan transkripsiya olish."""
        try:
            file_data = self.amocrm.download_file_from_url(audio_url)
            if not file_data:
                return None

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(file_data)
                temp_path = f.name

            try:
                audio_file = await self.client.aio.files.upload(file=temp_path)
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=[
                        audio_file,
                        "Bu audio yozuvni matnga o'gir. Faqat matnni qaytar, boshqa izoh yo'q.",
                    ],
                )
                return response.text if response.text else None
            finally:
                os.unlink(temp_path)

        except Exception as e:
            logger.warning(f"[CLASSIFIER] Audio transcription failed: {e}")
            return None

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Gemini javobini parse qilish."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "category": "unclear",
                "confidence": 0.0,
                "reason": "AI javobini parse qilib bo'lmadi",
                "evidence": [],
            }

    async def tag_unnecessary_leads(self, results: Optional[List[ClassificationResult]] = None):
        """Keraksiz sdelkalarni tag qilish."""
        targets = results or self.results
        tagged = 0

        for r in targets:
            if r.category == LeadCategory.PERSONAL and r.confidence >= 0.7:
                await self.amocrm.add_lead_tag(r.lead_id, "PERSONAL_NOT_CLIENT")
                tagged += 1
            elif r.category == LeadCategory.SPAM and r.confidence >= 0.7:
                await self.amocrm.add_lead_tag(r.lead_id, "SPAM_DETECTED")
                tagged += 1

        logger.info(f"[CLASSIFIER] {tagged} ta keraksiz sdelka belgilandi.")
        return tagged

    def get_summary(self) -> Dict[str, Any]:
        """Klassifikatsiya natijalarining xulosasi."""
        if not self.results:
            return {"total": 0, "categories": {}}

        categories = {}
        for cat in LeadCategory:
            items = [r for r in self.results if r.category == cat]
            if items:
                categories[cat.value] = {
                    "count": len(items),
                    "leads": [
                        {
                            "id": r.lead_id,
                            "name": r.lead_name,
                            "confidence": r.confidence,
                            "reason": r.reason,
                        }
                        for r in items
                    ],
                }

        return {
            "total": len(self.results),
            "categories": categories,
            "unnecessary_count": sum(
                1 for r in self.results
                if r.category in (LeadCategory.PERSONAL, LeadCategory.SPAM)
                and r.confidence >= 0.7
            ),
        }
