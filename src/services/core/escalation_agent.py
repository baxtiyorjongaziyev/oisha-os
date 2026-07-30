import logging
import datetime
from typing import Any, Dict, List, Optional

from src.database import Database
from src import config
from src.settings import settings

logger = logging.getLogger(__name__)

# task.kind qiymatlari (AgentTask.kind, proactive_worker.py) — Oisha jamoadan
# aniq reaksiya/hisobot talab qilgan xabar turlari.
SALES_ACCOUNTABILITY_KINDS = {"sales_conversion_push"}
PROJECT_ACCOUNTABILITY_KINDS = {"pm_stage_push", "daily_plan_demand"}
ACCOUNTABILITY_KINDS = (
    SALES_ACCOUNTABILITY_KINDS | PROJECT_ACCOUNTABILITY_KINDS | {"stagnation_alert"}
)


def _is_accountability_kind(task_kind: str) -> bool:
    if task_kind in ACCOUNTABILITY_KINDS:
        return True
    # Eski/legacy job nomlari uchun moslashuvchan (substring) tekshiruv.
    return "stagnation" in task_kind or "accountability" in task_kind


class EscalationAgent:
    """Oisha yuborgan xabarlarga javob qaytarilganini nazorat qiluvchi agent.

    Javobsiz qolgan ogohlantirishlarni bir martalik takrorlash o'rniga
    **vakolatlar darajasi** bo'yicha bosqichma-bosqich eskalatsiya qiladi:
    1) Xodim javob bermasa — uning bevosita rahbari (PM yoki sotuv menejeri)ga
       ma'lum qilinadi.
    2) Rahbar ham choralarni ko'rmasa (yoki zanjirda rahbar topilmasa) — Owner
       (@baxtiyorjong_gaziyev) ga eskalatsiya qilinadi.
    """

    def __init__(self, db: Database, bot_client=None):
        self.db = db
        self.bot_client = bot_client
        self.escalation_threshold_hours = 4

    async def check_pending_feedbacks(self):
        """Ogohlantirish xabarlariga javob berilmaganligini tekshirish va eskalatsiya qilish."""
        logger.info("[ESCALATION] Checking for unreplied alerts...")

        actions = await self.db.get_recent_agent_actions(limit=100)

        # source agent_execute action_id -> shu action bo'yicha eskalatsiya tarixi
        tracking: Dict[Any, List[Dict[str, Any]]] = {}
        pending: List[Dict[str, Any]] = []

        for action in actions:
            data = action["action_data"]
            if not isinstance(data, dict):
                continue

            if action["action_type"] in (
                "alert_manager_notified",
                "alert_escalated",
                "alert_replied",
            ):
                source_id = data.get("source_action_id")
                if source_id is not None:
                    tracking.setdefault(source_id, []).append(action)
                continue

            if action["action_type"] != "agent_execute":
                continue

            task_kind = str(data.get("task_kind", ""))
            if not _is_accountability_kind(task_kind):
                continue

            pending.append(action)

        for action in pending:
            try:
                await self._process_action(action, tracking.get(action["id"], []))
            except Exception as exc:
                logger.error(
                    f"[ESCALATION] Failed to process action {action.get('id')}: {exc}"
                )

    async def _process_action(
        self, action: Dict[str, Any], tracking_rows: List[Dict[str, Any]]
    ) -> None:
        target_user_id = action["user_id"]
        if not target_user_id:
            return

        if any(row["action_type"] == "alert_replied" for row in tracking_rows):
            return

        owner_rows = [r for r in tracking_rows if r["action_type"] == "alert_escalated"]
        if owner_rows:
            # Eng yuqori daraja (Owner) allaqachon xabardor qilingan.
            return

        created_at = self._parse_dt(action["created_at"])
        if not created_at:
            return

        manager_rows = [
            r for r in tracking_rows if r["action_type"] == "alert_manager_notified"
        ]

        if not manager_rows:
            if self._hours_since(created_at) < self.escalation_threshold_hours:
                return
            if await self._has_reply_since(target_user_id, action["created_at"]):
                await self._mark_replied(action, target_user_id)
                return
            await self._escalate_to_manager(action)
            return

        # Rahbar allaqachon xabardor qilingan — u yoki xodim shu vaqtdan beri
        # javob berdimi tekshiramiz.
        manager_action = manager_rows[0]
        manager_id = manager_action["action_data"].get("manager_id")
        notified_at = manager_action["created_at"]

        replied = await self._has_reply_since(target_user_id, notified_at)
        if not replied and manager_id:
            replied = await self._has_reply_since(manager_id, notified_at)
        if replied:
            await self._mark_replied(action, target_user_id)
            return

        notified_dt = self._parse_dt(notified_at)
        if not notified_dt or self._hours_since(notified_dt) < self.escalation_threshold_hours:
            return

        await self._escalate_to_owner(action, manager_id)

    async def _resolve_manager(
        self, task_kind: str, ignored_user_id: int
    ) -> Optional[int]:
        """Xodimning vakolat zanjiridagi bevosita rahbarini aniqlash."""
        if task_kind in SALES_ACCOUNTABILITY_KINDS:
            for mid in list(getattr(settings, "SALES_MANAGER_IDS", []) or []):
                if mid and int(mid) != int(ignored_user_id):
                    return int(mid)

        pm = await self.db.get_user_by_role("pm")
        if pm and pm.get("user_id") and int(pm["user_id"]) != int(ignored_user_id):
            return int(pm["user_id"])

        return None

    async def _escalate_to_manager(self, action: Dict[str, Any]) -> None:
        """Bevosita rahbarga (vakolat zanjirining 1-bosqichi) ma'lum qilish."""
        data = action["action_data"]
        target_user_id = action["user_id"]
        task_kind = str(data.get("task_kind", ""))
        goal = data.get("goal", "Noma'lum ogohlantirish")

        manager_id = await self._resolve_manager(task_kind, target_user_id)

        if not manager_id:
            # Vakolat zanjirida rahbar topilmadi — to'g'ridan-to'g'ri Ownerga o'tamiz.
            logger.info(
                f"[ESCALATION] No manager in chain for user {target_user_id}; "
                "escalating directly to Owner."
            )
            await self._escalate_to_owner(action, None)
            return

        if not self.bot_client:
            logger.error("[ESCALATION] Bot client missing. Cannot notify manager.")
            return

        user_info = await self.db.get_user_info(target_user_id)
        name = user_info["first_name"] if user_info else f"ID: {target_user_id}"
        username = (
            f"@{user_info['username']}"
            if user_info and user_info.get("username")
            else name
        )

        alert_text = (
            f"⚠️ <b>JAVOBSIZ OGOHLANTIRISH — RAHBARGA MA'LUM QILINDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Xodim:</b> {username}\n"
            f"📝 <b>Ogohlantirish:</b> {goal}\n"
            f"⏱ <b>Vaqt:</b> {action['created_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Ushbu xodim {self.escalation_threshold_hours} soatdan beri Oishaning "
            f"ogohlantirishiga javob bermadi. Iltimos, o'z vakolatingiz doirasida nazorat qiling."
        )

        try:
            await self.bot_client.send_message(manager_id, alert_text, parse_mode="html")
            await self.db.log_agent_action(
                target_user_id,
                "alert_manager_notified",
                {
                    "source_action_id": action["id"],
                    "manager_id": manager_id,
                    "goal": goal,
                    "notified_at": datetime.datetime.now().isoformat(),
                },
            )
            logger.info(
                f"[ESCALATION] Manager {manager_id} notified about unreplied user {target_user_id}."
            )
        except Exception as e:
            logger.error(f"[ESCALATION ERROR] Failed to notify manager {manager_id}: {e}")

    async def _escalate_to_owner(
        self, action: Dict[str, Any], manager_id: Optional[int]
    ) -> None:
        """Owner-ga eskalatsiya qilish (vakolat zanjirining yakuniy bosqichi)."""
        data = action["action_data"]
        target_user_id = action["user_id"]
        goal = data.get("goal", "Noma'lum ogohlantirish")

        owner_id = int(config.OWNER_ID or 0)
        if not owner_id or not self.bot_client:
            logger.error(
                "[ESCALATION] Owner ID or Bot Client missing. Cannot escalate."
            )
            return

        user_info = await self.db.get_user_info(target_user_id)
        name = user_info["first_name"] if user_info else f"ID: {target_user_id}"
        username = (
            f"@{user_info['username']}"
            if user_info and user_info.get("username")
            else name
        )

        manager_line = (
            f"👥 <b>Rahbar ham choralaridan bexabar</b> (ID: {manager_id})\n"
            if manager_id
            else ""
        )
        alert_text = (
            f"🚨 <b>ESKALATSIYA: JAVOB BERILMADI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Xodim:</b> {username}\n"
            f"📝 <b>Ogohlantirish:</b> {goal}\n"
            f"⏱ <b>Vaqt:</b> {action['created_at']}\n"
            f"{manager_line}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Ushbu xodim Oishaning ogohlantirishiga javob bermadi va vakolatlar "
            f"zanjiridagi eskalatsiya yakuniy bosqichga yetdi."
        )

        try:
            # Telethon yoki boshqa client orqali admin-ga yuborish
            await self.bot_client.send_message(owner_id, alert_text, parse_mode="html")

            await self.db.log_agent_action(
                target_user_id,
                "alert_escalated",
                {
                    "source_action_id": action["id"],
                    "manager_id": manager_id,
                    "goal": goal,
                    "escalated_at": datetime.datetime.now().isoformat(),
                },
            )
            logger.info(f"✅ Escalation message sent to Owner for user {target_user_id}")
        except Exception as e:
            logger.error(f"[ESCALATION ERROR] Failed to send message: {e}")

    async def _mark_replied(self, action: Dict[str, Any], user_id: int) -> None:
        logger.info(
            f"[ESCALATION] User {user_id} replied to alert. No escalation needed."
        )
        await self.db.log_agent_action(
            user_id,
            "alert_replied",
            {
                "source_action_id": action["id"],
                "goal": action["action_data"].get("goal"),
            },
        )

    async def _has_reply_since(self, user_id: Optional[int], since_iso: str) -> bool:
        if not user_id:
            return False
        conn = await self.db.get_connection()
        query = (
            "SELECT COUNT(*) FROM message_logs "
            "WHERE user_id = ? AND created_at > ? AND is_ai_reply = 0"
        )
        async with conn.execute(query, (user_id, since_iso)) as cursor:
            row = await cursor.fetchone()
        return bool(row and row[0])

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime.datetime]:
        try:
            return datetime.datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _hours_since(dt: datetime.datetime) -> float:
        return (datetime.datetime.now() - dt).total_seconds() / 3600
