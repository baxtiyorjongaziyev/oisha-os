"""
Oisha-OS: Telegram 3 yillik suhbatlar tarixini avtonom tahlil qilish va oʻrganish xizmati.

Ushbu xizmat fonda (background) sekin va xavfsiz tarzda:
- Barcha shaxsiy suhbatlar tarixini kezib chiqadi;
- Shaxsiy / oilaviy kontaktlarni avtomatik filtrlaydi;
- Ovozli xabarlarni Gemini STT orqali matnga oʻgiradi;
- 360° mijoz dosyesini tuzib, qayta sotuv (Re-engagement) imkoniyatlarini aniqlaydi;
- Jon Branding uchun eʼtirozlar va mijoz talablari bilimlar bazasini boyitadi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from telethon import TelegramClient

from src.services.ai.deal_activator import DealActivator
from src.services.ai.lead_profiler import TelegramLeadProfiler, TelegramLeadProfile
from src.services.core.stt_service import STTService
from src.services.corporate_sales.repository import CorporateSalesRepository

logger = logging.getLogger("TelegramHistoryCrawler")

_FAMILY_PATTERNS = re.compile(
    r"\b(onam|onajon|onajonim|dadam|otam|opam|singlim|akam|ukam|"
    r"oʻgʻlim|oglim|qizim|ayolim|xotinim|turmush|qoshni|qoʻshni|"
    r"togam|togʻam|ammam|xolam|pochcham|jiyanim)\b",
    re.IGNORECASE,
)


@dataclass
class CrawledLeadRecord:
    """Tahlil qilingan biznes-mijoz kartochkasi."""
    peer_id: int
    full_name: str
    username: str
    phone: str
    is_premium: bool
    business_domain: str
    estimated_role: str
    solvency_level: str
    lead_score: int
    key_icebreaker: str
    ready_to_send_script: str
    last_chat_snippet: str
    analyzed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TelegramHistoryCrawler:
    """Telegram tarixini xotirjam va avtonom tahlil qiluvchi servis."""

    def __init__(
        self,
        repo: CorporateSalesRepository,
        profiler: Optional[TelegramLeadProfiler] = None,
        activator: Optional[DealActivator] = None,
        stt: Optional[STTService] = None,
        rate_limit_seconds: float = 2.5,
    ) -> None:
        self.repo = repo
        self.profiler = profiler or TelegramLeadProfiler()
        self.activator = activator or DealActivator()
        self.stt = stt or STTService()
        self.rate_limit_seconds = rate_limit_seconds
        self._processed_peers: Set[int] = set()

    def is_personal_or_junk(self, entity: Any) -> bool:
        """Oilaviy, shaxsiy yoki xizmat akkauntlarini tekshirish."""
        if getattr(entity, "is_self", False):
            return True
        if getattr(entity, "bot", False):
            return True
        user_id = getattr(entity, "id", 0)
        if user_id in (777000, 42777):
            return True

        first_name = getattr(entity, "first_name", "") or ""
        last_name = getattr(entity, "last_name", "") or ""
        full_name = f"{first_name} {last_name}".strip()

        if _FAMILY_PATTERNS.search(full_name):
            return True
        return False

    async def _transcribe_if_voice(self, client: TelegramClient, msg: Any) -> str:
        """Ovozli, aylana video yoki rasmli xabarni matnga aylantirish."""
        is_video_note = bool(getattr(msg, "video_note", None))
        is_audio = bool(msg.voice or msg.audio)
        if not (is_video_note or is_audio):
            if msg.photo:
                cap = f": \"{msg.message}\"" if msg.message else ""
                return f"[Rasm{cap}]"
            if getattr(msg, "video", None):
                cap = f": \"{msg.message}\"" if msg.message else ""
                return f"[Video{cap}]"
            return msg.message or ""

        mime_type = "video/mp4" if is_video_note else "audio/ogg"
        prefix = "Aylana video xabar" if is_video_note else "Ovozli xabar"
        try:
            media_bytes = await client.download_media(msg, file=bytes)
            if media_bytes:
                res = await self.stt.transcribe(media_bytes, mime_type=mime_type)
                if res and res.transcript:
                    return f"[{prefix}: \"{res.transcript}\"]"
        except Exception as exc:
            logger.debug("[CRAWLER] %s transkriptida xatolik: %s", prefix, exc)

        dur_obj = getattr(msg, "video_note", None) or getattr(msg, "voice", None)
        dur = getattr(dur_obj, "duration", 0)
        dur_str = f" ({dur}s)" if dur else ""
        return f"[{prefix}{dur_str}]"

    async def extract_dialog_history(
        self, client: TelegramClient, peer: Any, limit: int = 15
    ) -> str:
        """Oxirgi xabarlar tarixini oʻqib, transkript tuzish."""
        lines = []
        async for msg in client.iter_messages(peer, limit=limit):
            sender = "Menejer" if msg.out else "Mijoz"
            text = await self._transcribe_if_voice(client, msg)
            if text.strip():
                lines.append(f"{sender}: {text.strip()}")
        lines.reverse()
        return "\n".join(lines)

    async def crawl_history(
        self,
        client: TelegramClient,
        *,
        max_dialogs: int = 500,
        progress_callback: Optional[Any] = None,
    ) -> List[CrawledLeadRecord]:
        """Tarixni toʻliq aylanib, biznes mijozlarni tahlil qilish."""
        results: List[CrawledLeadRecord] = []
        crawled_count = 0

        async for dialog in client.iter_dialogs(limit=max_dialogs):
            if not dialog.is_user:
                continue
            entity = dialog.entity
            user_id = getattr(entity, "id", 0)
            if user_id in self._processed_peers:
                continue

            if self.is_personal_or_junk(entity):
                self._processed_peers.add(user_id)
                continue

            first_name = getattr(entity, "first_name", "") or ""
            last_name = getattr(entity, "last_name", "") or ""
            full_name = f"{first_name} {last_name}".strip() or "Mijoz"
            phone = getattr(entity, "phone", "") or ""
            username = getattr(entity, "username", "") or ""

            crawled_count += 1
            if progress_callback:
                await progress_callback(crawled_count, full_name)

            try:
                transcript = await self.extract_dialog_history(client, entity, limit=15)
                if not transcript.strip() or len(transcript) < 30:
                    self._processed_peers.add(user_id)
                    continue

                raw_signals = await self.profiler.extract_raw_signals(client, entity)
                lead_profile = await self.profiler.analyze_lead(raw_signals, transcript)

                plan = await self.activator.generate_activation_plan(
                    transcript=transcript,
                    client_name=full_name,
                    idle_hours=48.0,
                )

                score = 85 if lead_profile.is_premium else 65
                record = CrawledLeadRecord(
                    peer_id=user_id,
                    full_name=full_name,
                    username=username,
                    phone=phone,
                    is_premium=lead_profile.is_premium,
                    business_domain=lead_profile.business_domain,
                    estimated_role=lead_profile.estimated_role,
                    solvency_level=lead_profile.solvency_level,
                    lead_score=score,
                    key_icebreaker=lead_profile.key_icebreaker,
                    ready_to_send_script=plan.ready_to_send_script,
                    last_chat_snippet=transcript[-200:],
                )
                results.append(record)
                self._processed_peers.add(user_id)

                await self._save_lead_to_db(record)

            except Exception as exc:
                logger.warning("[CRAWLER] %s tahlilida cheklov: %s", full_name, exc)

            await asyncio.sleep(self.rate_limit_seconds)

        return results

    async def _save_lead_to_db(self, lead: CrawledLeadRecord) -> None:
        """Tahlil qilingan lidni bazaga xavfsiz saqlash."""
        conn = await self.repo._get_conn()
        if not conn:
            return
        query = """
        INSERT INTO conversation_analyses (
            call_id, manager_id, manager_name,
            overall_score, deal_outcome, status,
            objections, recommendations, analyzed_at, updated_at
        ) VALUES (?, 1, 'TelegramCrawler', ?, 'sovuq_lid', 'arxivedan_topildi', ?, ?, ?, ?)
        ON CONFLICT(call_id) DO UPDATE SET
            overall_score = excluded.overall_score,
            deal_outcome = excluded.deal_outcome,
            updated_at = excluded.updated_at
        """
        try:
            cid = f"crawl_{lead.peer_id}"
            rec_json = json.dumps([lead.ready_to_send_script, lead.key_icebreaker])
            obj_json = json.dumps([lead.business_domain, lead.estimated_role])
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                query, (cid, lead.lead_score, obj_json, rec_json, now, now)
            )
            if hasattr(conn, "commit"):
                await conn.commit()
        except Exception as exc:
            logger.debug("[CRAWLER] DB saqlashda xato: %s", exc)

    def generate_digest_markdown(self, leads: List[CrawledLeadRecord]) -> str:
        """Tahlil qilingan lidlar boʻyicha ROP / Boshqaruvchi uchun hisobot."""
        lines = [
            "# 📈 TELEGRAM 3 YILLIK ARXIVI | AVTONOM TAHLIL HISOBOTI",
            f"**Tahlil sanasi:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Jami topilgan biznes-lidlar:** {len(leads)} ta",
            "",
            "## 🎯 Eng istiqbolli qayta sotuv (Re-engagement) imkoniyatlari:",
            "",
        ]
        for idx, lead in enumerate(leads[:20], 1):
            premium_badge = "⭐️ Premium" if lead.is_premium else "Oddiy"
            handle = f"@{lead.username}" if lead.username else f"+{lead.phone}" if lead.phone else "Kontakt"
            lines.extend([
                f"### {idx}. {lead.full_name} ({handle}) — {premium_badge}",
                f"- **Faoliyat:** {lead.business_domain} | **Lavozim:** {lead.estimated_role}",
                f"- **Xarid qobiliyati:** {lead.solvency_level}",
                f"- **Muz yorar mavzu:** {lead.key_icebreaker}",
                f"- **Yuborishga tayyor xabar:**",
                f"> \"{lead.ready_to_send_script}\"",
                "",
            ])
        return "\n".join(lines)
