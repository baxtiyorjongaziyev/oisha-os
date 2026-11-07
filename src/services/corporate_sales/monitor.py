"""
Korporativ sotuvchilar Telegram muloqotlarini monitoring qilish xizmati.
Telethon mijozlari orqali read-only rejimda ishlaydi va suhbatlarni tahlil qiladi.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from src.services.ai.quality_analyzer import QualityAnalyzer
from src.services.corporate_sales.models import (
    ConversationBuffer,
    CorporateSeller,
    MessageSenderType,
    MonitoredChatMessage,
)
from src.services.corporate_sales.repository import CorporateSalesRepository
from src.services.corporate_sales.reporter import CorporateSalesReporter
from src.settings import settings

logger = logging.getLogger("CorporateSalesMonitor")


class CorporateSalesMonitor:
    """Koʻp akkauntli korporativ sotuv monitoringi dvigateli."""

    def __init__(
        self,
        repository: CorporateSalesRepository,
        reporter: CorporateSalesReporter,
        quality_analyzer: Optional[QualityAnalyzer] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        idle_timeout_seconds: int = 300,
    ):
        self.repo = repository
        self.reporter = reporter
        self.analyzer = quality_analyzer or QualityAnalyzer()
        self.api_id = api_id or getattr(settings, "API_ID", None) or 2040
        self.api_hash = (
            api_hash
            or getattr(settings, "API_HASH", None)
            or "b18441a1ff607e10a989891a5462e627"
        )
        self.idle_timeout = idle_timeout_seconds

        # seller_id -> TelegramClient
        self.clients: Dict[int, Any] = {}
        # (seller_id, client_peer_id) -> ConversationBuffer
        self.buffers: Dict[Tuple[int, int], ConversationBuffer] = {}
        self._running = False
        self._watcher_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Ombor jadvallarini ishga tushirish."""
        await self.repo.init_tables()

    def get_active_buffer(
        self, seller: CorporateSeller, peer_id: int, peer_name: str = ""
    ) -> ConversationBuffer:
        """Mavjud buferni olish yoki yangisini yaratish."""
        key = (seller.seller_id, peer_id)
        if key not in self.buffers:
            self.buffers[key] = ConversationBuffer(
                seller_id=seller.seller_id,
                seller_name=seller.name,
                client_peer_id=peer_id,
                client_name=peer_name,
            )
        return self.buffers[key]

    async def handle_new_message(
        self,
        seller: CorporateSeller,
        *,
        peer_id: int,
        message_id: int,
        text: str,
        is_outgoing: bool,
        sender_name: str = "",
        is_voice: bool = False,
        voice_duration: int = 0,
    ) -> None:
        """Kelgan yoki ketgan yangi xabarni qayta ishlash."""
        buffer = self.get_active_buffer(seller, peer_id, peer_name=sender_name)
        sender_type = (
            MessageSenderType.SELLER if is_outgoing else MessageSenderType.CLIENT
        )
        msg_obj = MonitoredChatMessage(
            message_id=message_id,
            sender_type=sender_type,
            sender_name=seller.name if is_outgoing else (sender_name or "Mijoz"),
            text=text or "",
            is_voice=is_voice,
            duration_seconds=voice_duration,
        )
        buffer.add_message(msg_obj)
        logger.debug(
            "[MONITOR] Xabar qoʻshildi: seller=%s, peer=%s, msg_count=%s",
            seller.name,
            peer_id,
            buffer.get_message_count(),
        )

    async def analyze_and_flush_buffer(
        self, key: Tuple[int, int], buffer: ConversationBuffer
    ) -> bool:
        """Yetarli hajmga yetgan suhbatni tahlil qilib, natijani yuborish."""
        if not buffer.is_substantive():
            logger.info(
                "[MONITOR] Suhbat hajm jihatidan yetarli emas, tahlilsiz tozalandi: %s",
                key,
            )
            buffer.clear()
            return False

        seller_id, client_peer_id = key
        conversation_id = f"corp_{seller_id}_{client_peer_id}_{int(buffer.last_activity_at.timestamp())}"
        transcript = buffer.to_transcript()

        try:
            analysis = await self.analyzer.analyze_conversation_ai(
                conversation_text=transcript,
                conversation_id=conversation_id,
                manager_id=seller_id,
                manager_name=buffer.seller_name,
            )

            # Tahlil natijalarini ajratib olish
            overall_score = getattr(analysis, "overall_score", 0)
            deal_outcome = getattr(analysis, "outcome", "aniqlanmadi")
            strengths = getattr(analysis, "strengths", [])
            weaknesses = getattr(analysis, "weaknesses", [])
            objections = getattr(analysis, "objections_detected", [])
            recommendations = getattr(analysis, "action_items", [])

            # 1. DB ga saqlash
            await self.repo.save_conversation_analysis(
                conversation_id=conversation_id,
                manager_id=seller_id,
                manager_name=buffer.seller_name,
                overall_score=overall_score,
                deal_outcome=deal_outcome,
                objections=objections,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
            )

            # 2. Hisobot yetkazish
            seller_phone = buffer.client_phone or ""
            await self.reporter.deliver_report(
                seller_name=buffer.seller_name,
                seller_phone=seller_phone,
                client_name=buffer.client_name,
                client_handle=buffer.client_username,
                overall_score=overall_score,
                deal_outcome=deal_outcome,
                strengths=strengths,
                weaknesses=weaknesses,
                objections=objections,
                recommendations=recommendations,
            )

            logger.info(
                "[MONITOR] Suhbat muvaffaqiyatli tahlil qilindi: %s (baho: %s)",
                conversation_id,
                overall_score,
            )
            buffer.clear()
            return True

        except Exception as exc:
            logger.error("[MONITOR] Tahlil jarayonida xatolik: %s", exc)
            return False

    async def check_all_idle_buffers(self) -> int:
        """Tinch turgan barcha suhbatlarni tekshirish va tahlil qilish."""
        analyzed_count = 0
        keys_to_check = list(self.buffers.keys())

        for key in keys_to_check:
            buf = self.buffers.get(key)
            if buf and buf.is_idle(timeout_seconds=self.idle_timeout):
                if buf.is_substantive():
                    ok = await self.analyze_and_flush_buffer(key, buf)
                    if ok:
                        analyzed_count += 1
                else:
                    buf.clear()

        return analyzed_count

    async def _watcher_loop(self) -> None:
        """Fon rejimida har daqiqada tinch turgan suhbatlarni tekshirib boruvchi sikl."""
        while self._running:
            try:
                await self.check_all_idle_buffers()
            except Exception as exc:
                logger.error("[MONITOR] Watcher loop xatosi: %s", exc)
            await asyncio.sleep(30)

    async def start(self) -> None:
        """Monitoring tizimini toʻliq ishga tushirish."""
        if self._running:
            return
        await self.initialize()
        self._running = True
        self._watcher_task = asyncio.create_task(self._watcher_loop())
        logger.info("[MONITOR] Corporate Sales Monitor ishga tushirildi")

    async def stop(self) -> None:
        """Monitoring tizimini toʻxtatish."""
        self._running = False
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None

        # Mijozlarni xavfsiz uzish
        for seller_id, client in self.clients.items():
            try:
                if hasattr(client, "disconnect"):
                    await client.disconnect()
            except Exception as exc:
                logger.warning("[MONITOR] Client #%s ni uzishda xato: %s", seller_id, exc)

        self.clients.clear()
        logger.info("[MONITOR] Corporate Sales Monitor toʻxtatildi")
