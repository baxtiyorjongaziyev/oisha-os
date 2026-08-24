"""Fireflies.ai Audio Calling and Meeting Sync Integration for Oisha-OS."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from src.context import app_ctx
from src.database import Database
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

logger = logging.getLogger("FirefliesSync")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\+?[0-9]{9,15}")


class FirefliesSync:
    """Fireflies.ai GraphQL and Webhook Sync Engine."""

    ENDPOINT = "https://api.fireflies.ai/graphql"

    def __init__(
        self,
        api_key: Optional[str] = None,
        db: Optional[Database] = None,
        amocrm: Optional[Any] = None,
    ):
        raw_key = api_key or (
            settings.FIREFLIES_API_KEY.get_secret_value()
            if getattr(settings, "FIREFLIES_API_KEY", None)
            else os.getenv("FIREFLIES_API_KEY", "")
        )
        self.api_key = str(raw_key or "").strip()
        self.enabled = bool(getattr(settings, "ENABLE_FIREFLIES_SYNC", True)) and bool(self.api_key)
        self.db = db
        if amocrm is not None:
            self.amocrm = amocrm
        else:
            try:
                secret_val = (
                    settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                    if getattr(settings, "AMOCRM_CLIENT_SECRET", None)
                    else ""
                )
                self.amocrm = AmoCRMSync(
                    subdomain=getattr(settings, "AMOCRM_SUBDOMAIN", "") or "jonbranding",
                    client_id=getattr(settings, "AMOCRM_CLIENT_ID", "") or "",
                    client_secret=secret_val,
                    redirect_url=getattr(settings, "AMOCRM_REDIRECT_URL", "") or "",
                )
            except Exception:
                self.amocrm = None
        self.manager_name = str(getattr(settings, "FIREFLIES_MANAGER_NAME", "") or "").lower()

    async def fetch_transcript(self, transcript_id: str) -> Optional[Dict[str, Any]]:
        """Fetch transcript and speaker sentences from Fireflies GraphQL."""
        if not self.api_key:
            logger.warning("[FIREFLIES] API key missing; cannot fetch transcript %s", transcript_id)
            return None

        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                duration
                organizer_email
                participants
                sentences {
                    text
                    speaker_name
                    start_time
                    end_time
                }
            }
        }
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.ENDPOINT,
                    json={"query": query, "variables": {"id": str(transcript_id)}},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                t = data.get("data", {}).get("transcript")
                return t if isinstance(t, dict) else None
        except Exception as exc:
            logger.error("[FIREFLIES] GraphQL fetch failed for %s: %s", transcript_id, exc)
            return None

    def normalize_dialogue(self, transcript_data: Dict[str, Any]) -> str:
        """Format sentences into structured dialogue with speaker labels."""
        sentences = transcript_data.get("sentences") or []
        first_speaker = None
        lines = []

        for s in sentences:
            speaker = str(s.get("speaker_name") or "Spiker").strip()
            if first_speaker is None:
                first_speaker = speaker

            is_manager = (
                self.manager_name in speaker.lower()
                if self.manager_name
                else speaker == first_speaker
            )
            role = "Menejer" if is_manager else "Mijoz"
            text = str(s.get("text") or "").strip()
            if text:
                lines.append(f"{role} ({speaker}): {text}")

        return "\n".join(lines)

    async def process_transcript(self, transcript_id: str) -> Dict[str, Any]:
        """Full pipeline: Ingest -> Diarize -> AI Analysis -> AmoCRM Writeback -> Telegram Alert -> SalesCoach."""
        logger.info("[FIREFLIES] Processing transcript %s...", transcript_id)
        transcript_data = await self.fetch_transcript(transcript_id)
        if not transcript_data:
            return {"status": "error", "message": "Transcript not found or empty"}

        title = str(transcript_data.get("title") or "Meeting")
        duration_sec = int(transcript_data.get("duration") or 0)
        participants = transcript_data.get("participants") or []
        organizer = str(transcript_data.get("organizer_email") or "")
        dialogue_text = self.normalize_dialogue(transcript_data)

        if not dialogue_text:
            return {"status": "skipped", "message": "No dialogue sentences found"}

        # 1. AI Analysis via CallAnalyzer logic
        from src.services.core.call_analyzer import CallAnalyzer

        analyzer = CallAnalyzer(amocrm=self.amocrm, db=self.db)
        analysis = await analyzer.analyze_transcript(dialogue_text, duration_sec or 180)

        category = analysis.get("category") or "Mijoz"
        client_mood = analysis.get("client_mood") or "Ijobiy"
        summary = analysis.get("summary") or title
        next_steps = analysis.get("next_steps") or "N/A"
        outcome = analysis.get("natija") or analysis.get("outcome") or ""

        # 2. Match AmoCRM Lead
        lead_id = await self._find_matching_lead(title=title, participants=participants, organizer=organizer)

        # 3. Writeback to AmoCRM
        task_id = None
        if lead_id:
            note_content = (
                f"🎙 🔥 <b>Fireflies AI Meeting Tahlili: {title}</b>\n\n"
                f"⏱ Davomiyligi: {duration_sec // 60}m {duration_sec % 60}s\n"
                f"📊 Xulosa: {summary}\n"
                f"🎯 Keyingi qadam: {next_steps}\n"
                f"🎭 Kayfiyat: {client_mood} | Toifa: {category}\n"
            )
            if outcome:
                note_content += f"🏆 Natija: {outcome}\n"
            note_content += f"\n📝 Transkript parchasi:\n{dialogue_text[:1500]}"

            try:
                await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, note_content)
                await asyncio.to_thread(self.amocrm.add_lead_tag, lead_id, "Fireflies-AI")
            except Exception as e:
                logger.error("[FIREFLIES] Error writing note to AmoCRM lead %s: %s", lead_id, e)

            # Create follow-up task
            try:
                task_id = await analyzer._create_follow_up_task(
                    lead_id=lead_id,
                    category=category,
                    summary=summary,
                    client_mood=client_mood,
                    next_steps=next_steps,
                    responsible_user_id=None,
                    agreed_datetime=analysis.get("kelishilgan_vaqt"),
                )
            except Exception as e:
                logger.error("[FIREFLIES] Task creation error for lead %s: %s", lead_id, e)

        # 4. Notify Telegram Group
        await self._notify_telegram(
            transcript_id=transcript_id,
            title=title,
            duration_sec=duration_sec,
            summary=summary,
            client_mood=client_mood,
            category=category,
            next_steps=next_steps,
            lead_id=lead_id,
            task_id=task_id,
            analysis=analysis,
        )

        # 5. Forward to SalesCoach-AI
        try:
            from src.services.core.salescoach_sync import get_salescoach_sync

            salescoach = get_salescoach_sync()
            if salescoach.enabled and salescoach.base_url:
                secret = getattr(settings, "SALESCOACH_SERVICE_TOKEN", None)
                token_val = secret.get_secret_value() if secret else ""
                headers = {"x-webhook-secret": token_val} if token_val else {}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{salescoach.base_url}/integrations/call-intel/fireflies",
                        json={"meetingId": transcript_id, "title": title},
                        headers=headers,
                    )
        except Exception as sc_err:
            logger.warning("[FIREFLIES] Forward to salescoach-ai skipped: %s", sc_err)

        return {
            "status": "success",
            "transcript_id": transcript_id,
            "lead_id": lead_id,
            "summary": summary,
            "task_id": task_id,
        }

    async def _find_matching_lead(
        self, title: str, participants: List[Any], organizer: str
    ) -> Optional[int]:
        """Try matching an AmoCRM lead by phone number, email, or client name."""
        all_text = f"{title} {' '.join(str(p) for p in participants)} {organizer}"

        phones = _PHONE_RE.findall(all_text)
        for phone in phones:
            clean_phone = phone.replace("+", "").replace(" ", "").strip()
            if len(clean_phone) >= 9:
                try:
                    leads = await asyncio.to_thread(self.amocrm.search_leads, clean_phone)
                    if leads and isinstance(leads, list):
                        return int(leads[0].get("id"))
                except Exception:
                    pass

        emails = _EMAIL_RE.findall(all_text)
        for email in emails:
            if "jonbranding" not in email.lower() and "fireflies" not in email.lower():
                try:
                    leads = await asyncio.to_thread(self.amocrm.search_leads, email)
                    if leads and isinstance(leads, list):
                        return int(leads[0].get("id"))
                except Exception:
                    pass

        return None

    async def _notify_telegram(
        self,
        transcript_id: str,
        title: str,
        duration_sec: int,
        summary: str,
        client_mood: str,
        category: str,
        next_steps: str,
        lead_id: Optional[int],
        task_id: Optional[str],
        analysis: Dict[str, Any],
    ) -> None:
        """Send formatted alert to Sales/CRM Telegram group."""
        try:
            from src.api.routes.state import api_state

            bot_client = getattr(api_state, "bot_client", None) or getattr(app_ctx, "bot_runtime", None)
            if not bot_client:
                return

            target_chat_id = getattr(settings, "AMOCRM_ALERT_FORWARD_GROUP_ID", None) or getattr(settings, "CRM_GROUP_ID", None)
            topic_id = getattr(settings, "AMOCRM_ALERT_FORWARD_TOPIC_ID", None)
            if not target_chat_id:
                return

            dur_m = duration_sec // 60
            dur_s = duration_sec % 60
            subdomain = getattr(self.amocrm, "subdomain", "jonbranding")

            lead_str = f"<a href=\"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}\">AmoCRM #{lead_id}</a>" if lead_id else "Bog'lanmagan"

            msg = (
                f"🎙 🔥 <b>Fireflies Uchrashuv Tahlili (Call Intelligence)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Mavzu:</b> {title}\n"
                f"👤 <b>Lid:</b> {lead_str}\n"
                f"⏱ <b>Davomiyligi:</b> {dur_m}m {dur_s}s\n"
                f"🎭 <b>Kayfiyat:</b> {client_mood} | <b>Toifa:</b> {category}\n"
                f"📝 <b>Xulosa:</b> {summary}\n"
                f"🎯 <b>Keyingi qadam:</b> {next_steps}\n"
            )
            if task_id:
                msg += f"✅ <b>AmoCRM Vazifasi:</b> Biriktirildi (Task #{task_id})\n"

            kwargs: Dict[str, Any] = {"parse_mode": "HTML", "disable_web_page_preview": True}
            if topic_id:
                kwargs["reply_to_message_id"] = topic_id

            if hasattr(bot_client, "send_message"):
                await bot_client.send_message(chat_id=target_chat_id, text=msg, **kwargs)
        except Exception as exc:
            logger.warning("[FIREFLIES] Telegram notification failed: %s", exc)


app_ctx.fireflies_sync: Optional[FirefliesSync] = None


def get_fireflies_sync() -> FirefliesSync:
    if getattr(app_ctx, "fireflies_sync", None) is None:
        app_ctx.fireflies_sync = FirefliesSync()
    return app_ctx.fireflies_sync
