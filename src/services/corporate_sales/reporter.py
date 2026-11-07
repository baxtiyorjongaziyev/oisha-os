"""
Korporativ sotuv tahlili boʻyicha hisobotlar va bildirishnomalar generatsiyasi.
ROP (savdo rahbari) guruhi va amoCRM uchun formatlangan xabarlar.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CorporateSalesReporter")


class CorporateSalesReporter:
    """Sotuv tahlili hisobotlarini shakllantirish va yuborish."""

    def __init__(
        self,
        bot_client: Any = None,
        rop_chat_id: Optional[int] = None,
        amocrm_client: Any = None,
    ):
        self.bot_client = bot_client
        self.rop_chat_id = rop_chat_id
        self.amocrm = amocrm_client

    @staticmethod
    def _get_score_badge(score: int) -> str:
        """Ballga qarab rangli belgi qaytarish."""
        if score >= 80:
            return f"🟢 {score}/100 (Namunali)"
        if score >= 60:
            return f"🟡 {score}/100 (Oʻrtacha)"
        return f"🔴 {score}/100 (Tanqidiy - tuzatish zarur)"

    def format_rop_report(
        self,
        *,
        seller_name: str,
        seller_phone: str,
        client_name: str,
        client_handle: str,
        overall_score: int,
        deal_outcome: str,
        stages: Optional[List[Dict[str, Any]]] = None,
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        objections: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> str:
        """ROP uchun chiroyli oʻzbekcha hisobot matnini tuzish."""
        badge = self._get_score_badge(overall_score)
        client_display = client_name or client_handle or "Nomaʼlum mijoz"
        handle_part = f" ({client_handle})" if client_handle else ""

        lines = [
            "📊 **JON BRANDING | MENEJER SUHBATI TAHLILI**",
            "──────────────────────────",
            f"👤 **Menejer:** {seller_name} ({seller_phone})",
            f"🤝 **Mijoz:** {client_display}{handle_part}",
            f"⭐ **Sifat bali:** {badge}",
            f"🎯 **Natija:** {deal_outcome}",
        ]

        if objections:
            clean_objs = [o for o in objections if o]
            if clean_objs:
                lines.append(f"💬 **Eʼtirozlar:** {', '.join(clean_objs)}")

        if strengths:
            lines.append("\n✅ **Kuchli tomonlari:**")
            for item in strengths[:3]:
                lines.append(f"  • {item}")

        if weaknesses:
            lines.append("\n⚠️ **Oʻsish nuqtalari (Xatolar):**")
            for item in weaknesses[:3]:
                lines.append(f"  • {item}")

        if recommendations:
            lines.append("\n💡 **ROP uchun tavsiya:**")
            for item in recommendations[:2]:
                lines.append(f"  👉 {item}")

        lines.append("──────────────────────────")
        lines.append("🤖 *Oisha-OS Sales Quality Sentinel*")
        return "\n".join(lines)

    async def send_to_rop(
        self,
        report_text: str,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Hisobotni ROP Telegram guruhiga yuborish."""
        target_chat = chat_id or self.rop_chat_id
        if not self.bot_client:
            logger.warning("[REPORTER] Telegram client yoʻq, xabar yuborilmadi")
            return False
        if not target_chat:
            logger.warning("[REPORTER] ROP chat_id koʻrsatilmagan")
            return False

        try:
            if hasattr(self.bot_client, "send_message"):
                await self.bot_client.send_message(
                    chat_id=target_chat,
                    text=report_text,
                    parse_mode="Markdown",
                )
            elif hasattr(self.bot_client, "send_message_async"):
                await self.bot_client.send_message_async(target_chat, report_text)
            logger.info("[REPORTER] ROP hisoboti yuborildi: chat_id=%s", target_chat)
            return True
        except Exception as exc:
            logger.error("[REPORTER] ROP guruhiga yuborishda xato: %s", exc)
            return False

    async def sync_to_amocrm_lead(
        self,
        lead_id: int,
        report_text: str,
    ) -> bool:
        """amoCRM bitimi ichiga eslatma (note) qoʻshish."""
        if not self.amocrm:
            return False
        if not lead_id:
            return False

        try:
            if hasattr(self.amocrm, "add_lead_note"):
                await self.amocrm.add_lead_note(
                    lead_id=lead_id,
                    text=f"AI Sales Coach tahlili:\n{report_text}",
                )
            elif hasattr(self.amocrm, "add_note"):
                await self.amocrm.add_note(
                    element_id=lead_id,
                    element_type="leads",
                    text=report_text,
                )
            logger.info("[REPORTER] amoCRM lead #%s ga izoh qoʻshildi", lead_id)
            return True
        except Exception as exc:
            logger.error("[REPORTER] amoCRM ga yozishda xato: %s", exc)
            return False

    async def deliver_report(
        self,
        *,
        seller_name: str,
        seller_phone: str,
        client_name: str,
        client_handle: str,
        overall_score: int,
        deal_outcome: str,
        stages: Optional[List[Dict[str, Any]]] = None,
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        objections: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        lead_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> str:
        """Hisobotni shakllantirib, tegishli kanallarga yetkazish."""
        report_text = self.format_rop_report(
            seller_name=seller_name,
            seller_phone=seller_phone,
            client_name=client_name,
            client_handle=client_handle,
            overall_score=overall_score,
            deal_outcome=deal_outcome,
            stages=stages,
            strengths=strengths,
            weaknesses=weaknesses,
            objections=objections,
            recommendations=recommendations,
        )
        await self.send_to_rop(report_text, chat_id=chat_id)
        if lead_id:
            await self.sync_to_amocrm_lead(lead_id, report_text)
        return report_text
