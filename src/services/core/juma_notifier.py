"""Avtomatlashtirilgan Juma tabriklari (oisha.service ichidan, alohida sessiyasiz)."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, InputUserDeactivatedError, PeerFloodError, PeerIdInvalidError,
    UserNotMutualContactError, UserPrivacyRestrictedError, UsernameInvalidError,
    UsernameNotOccupiedError,
)

from src.database import Database
from src.services.core.customer_outbound_policy import automatic_customer_send_allowed
from src.services.core.juma_guard import (
    JUMA_TEMPLATES, TASHKENT_TZ, JumaRateConfig, classify_and_order_recipients,
    compute_juma_deadline, is_excluded_member, is_juma_send_window, is_quiet_hours,
    is_silent_send_time, load_custom_greetings, load_juma_rate_config, match_group_dialogs,
    next_delay_seconds, pick_greeting_text, seconds_until_quiet_ends, select_target_groups,
)
from src.settings import settings

logger = logging.getLogger(__name__)
_SKIP_ERRORS = (
    UserPrivacyRestrictedError, UserNotMutualContactError, InputUserDeactivatedError,
    PeerIdInvalidError, UsernameNotOccupiedError, UsernameInvalidError,
)


def _as_tashkent(dt: datetime) -> datetime:
    return dt.replace(tzinfo=TASHKENT_TZ) if dt.tzinfo is None else dt.astimezone(TASHKENT_TZ)


async def _iter_async_or_empty(obj: Any) -> list[Any]:
    if inspect.iscoroutine(obj):
        obj.close()
        return []
    return [item async for item in obj] if hasattr(obj, "__aiter__") else []


def _is_client_connected(client: Any) -> bool:
    if client is None:
        return False
    fn = getattr(client, "is_connected", None)
    if not callable(fn):
        return True
    res = fn()
    if inspect.iscoroutine(res):
        res.close()
        return True
    return bool(res)


async def _send_with_typing(
    client: TelegramClient, peer_id: int, text: str, config: JumaRateConfig, *, silent: bool
) -> None:
    typing_sec = random.uniform(config.typing_min_sec, config.typing_max_sec)
    with contextlib.suppress(Exception):
        act = client.action(peer_id, "typing")
        if inspect.iscoroutine(act):
            act.close()
        elif hasattr(act, "__aenter__"):
            async with act:
                await asyncio.sleep(typing_sec)
    await client.send_message(peer_id, text, silent=silent)


async def _deliver_one_message(
    client: TelegramClient, peer: dict, text: str, config: JumaRateConfig, *, silent: bool
) -> tuple[str, Optional[str]]:
    """Yagona foydalanuvchiga typing + anti-spam xatolarni ushlash bilan yuboradi."""
    try:
        await _send_with_typing(client, peer["id"], text, config, silent=silent)
        return "sent", None
    except PeerFloodError:
        return "abort", "PeerFloodError"
    except FloodWaitError as exc:
        if exc.seconds > config.max_flood_wait_sec:
            return "abort", f"FloodWait {exc.seconds}s > {config.max_flood_wait_sec}s"
        await asyncio.sleep(exc.seconds + 5)
        try:
            await _send_with_typing(client, peer["id"], text, config, silent=silent)
            return "sent", None
        except PeerFloodError:
            return "abort", "PeerFloodError (retry)"
        except Exception as retry_exc:
            logger.warning("[JUMA] Retry failed for %s: %s", peer["id"], retry_exc)
            return "skip", None
    except _SKIP_ERRORS as exc:
        logger.info("[JUMA] Skip %s: %s", peer["id"], type(exc).__name__)
        return "skip", None
    except Exception as exc:
        logger.error("[JUMA ERROR] %s: %s", peer["id"], exc)
        return "skip", None


class JumaNotifier:
    """Automated Friday Greetings for TN7/TNx Classmates inside oisha.service."""

    def __init__(
        self, client: TelegramClient, db: Database, group_id: int = None,
        notify_fn: Optional[Callable[[str], Awaitable[Any]]] = None,
    ):
        self.client = client
        self.db = db
        self.group_id = group_id
        self.notify_fn = notify_fn
        self.RUN_WINDOW_START = datetime.strptime("06:00", "%H:%M").time()
        self.RUN_WINDOW_END = datetime.strptime("17:00", "%H:%M").time()
        self._lock = asyncio.Lock()

    async def _notify_owner(self, text: str) -> None:
        if not self.notify_fn:
            return
        try:
            res = self.notify_fn(text)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            logger.warning("[JUMA] Owner notify error: %s", exc)

    async def check_and_send(self, *, now: Optional[datetime] = None, force_enabled: bool = False) -> bool:
        """Juma 06:00–17:00 Toshkent oynasida navbatdagi tabrikni ishga tushiradi."""
        if not force_enabled and os.getenv("ENABLE_JUMA_NOTIFIER", "").strip().lower() not in {"1", "true", "yes", "on"}:
            logger.info("[JUMA] Disabled. Set ENABLE_JUMA_NOTIFIER=1 to enable.")
            return False
        config = load_juma_rate_config()
        current = _as_tashkent(now or datetime.now(TASHKENT_TZ))
        if not automatic_customer_send_allowed("juma", now=current):
            return False
        if not is_juma_send_window(current, config) or is_quiet_hours(current, config):
            return False
        if not _is_client_connected(self.client):
            logger.warning("[JUMA] Telethon client ulanmagan — keyingi siklda qayta uriniladi.")
            return False
        today_str = compute_juma_deadline(current, config).strftime("%Y-%m-%d")
        if self._lock.locked() or await self._is_already_sent(today_str):
            return False
        async with self._lock:
            if await self._is_already_sent(today_str):
                return False
            logger.info("[JUMA] Starting Friday TN7 greeting delivery for %s.", today_str)
            await self.send_greetings(today_str, now=now)
            return True

    async def _is_already_sent(self, date_str: str) -> bool:
        try:
            return await self.db.is_job_run("juma_mubarak", date_str)
        except Exception as exc:
            logger.error("[JUMA DB ERROR] check: %s", exc)
            return False

    async def _mark_as_sent(self, date_str: str) -> None:
        try:
            await self.db.mark_job_run("juma_mubarak", date_str)
        except Exception as exc:
            logger.error("[JUMA DB ERROR] mark: %s", exc)

    async def _fetch_group_users(self, group: dict, dialogs: list[Any]) -> list[Any]:
        users: list[Any] = []
        exact = [d for d in dialogs if getattr(d, "id", None) == group["id"]]
        for dialog in exact:
            users.extend(await _iter_async_or_empty(self.client.iter_participants(dialog)))
        if not users:
            try:
                users.extend(await self.client.get_participants(group["id"], limit=500) or [])
            except Exception as exc:
                logger.error("[JUMA] Group %s crawl error: %s", group["id"], exc)
        if not users and not exact:
            for dialog in match_group_dialogs(dialogs, group):
                users.extend(await _iter_async_or_empty(self.client.iter_participants(dialog)))
        return users

    async def collect_recipients(self, config: JumaRateConfig) -> tuple[list[dict], int]:
        """Maqsad guruhlardan unikal aʼzolarni yigʻadi va PCG/raqiblarni filtrlaydi."""
        dialogs = await _iter_async_or_empty(self.client.iter_dialogs())
        existing_dm_ids = {d.entity.id for d in dialogs if getattr(d, "is_user", False) and getattr(d, "entity", None) is not None}
        target_groups = select_target_groups(os.getenv("JUMA_TARGET_GROUPS", "TN7"))
        if self.group_id and all(g["id"] != self.group_id for g in target_groups):
            target_groups.append({"label": f"Group {self.group_id}", "code": str(self.group_id), "names": [], "id": self.group_id})
        seen_ids: set[int] = set()
        recipients: list[dict] = []
        excluded_count = 0
        for group in target_groups:
            for u in await self._fetch_group_users(group, dialogs):
                if getattr(u, "bot", False) or getattr(u, "deleted", False) or getattr(u, "is_self", False) or u.id in seen_ids:
                    continue
                seen_ids.add(u.id)
                uname = getattr(u, "username", None) or ""
                full_name = f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}".strip()
                if is_excluded_member({"id": u.id, "username": uname, "name": full_name}, config, excluded_names=settings.EXCLUDED_NAMES)[0]:
                    excluded_count += 1
                    continue
                mutual = bool(getattr(u, "mutual_contact", False))
                recipients.append({
                    "id": u.id, "username": uname,
                    "name": full_name or getattr(u, "first_name", "") or "Doʻstim",
                    "group": group["label"], "mutual": mutual, "warm": mutual or (u.id in existing_dm_ids),
                })
        return recipients, excluded_count

    async def get_tn5_classmates(self) -> list[dict]:
        """Backward-compatible wrapper returning filtered classmates."""
        config = load_juma_rate_config()
        classmates: list[dict] = []
        try:
            conn = await self.db.get_connection()
            query = (
                "SELECT user_id, first_name, username FROM users "
                "WHERE (last_name LIKE '%TN%' OR first_name LIKE '%TN%' OR contact_name LIKE '%TN%') "
                "OR (last_name LIKE '%Tez Natija%' OR first_name LIKE '%Tez Natija%')"
            )
            async with conn.execute(query) as cursor:
                for r in await cursor.fetchall():
                    if not is_excluded_member({"id": r[0], "username": r[2], "name": r[1]}, config, excluded_names=settings.EXCLUDED_NAMES)[0]:
                        classmates.append({"id": r[0], "name": r[1], "username": r[2]})
        except Exception as exc:
            logger.error("[JUMA DB ERROR] fetch: %s", exc)
        seen_ids = {c["id"] for c in classmates}
        group_users, _ = await self.collect_recipients(config)
        classmates.extend(u for u in group_users if u["id"] not in seen_ids)
        return classmates

    async def _fetch_last_sent_map(self, conn: Any) -> dict[int, str]:
        query = "SELECT user_id, MAX(run_date) FROM juma_sent_logs GROUP BY user_id"
        try:
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
        except Exception as exc:
            logger.warning("[JUMA DB WARN] history query: %s", exc)
            return {}
        return {int(r[0]): str(r[1]) for r in rows if r and r[0] is not None and r[1]}

    async def _filter_eligible_recipients(
        self, conn: Any, recipients: list[dict], date_str: str
    ) -> list[dict]:
        """Bugun va (oylik rejimda) joriy oyda olganlarni chiqaradi, qolganlarini navbatlaydi."""
        last_sent = await self._fetch_last_sent_map(conn)
        mode = os.getenv("JUMA_REPEAT_MODE", "monthly").strip().lower()
        month_prefix = f"{date_str[:7]}-"
        eligible: list[dict] = []
        for peer in recipients:
            last_date = last_sent.get(peer["id"], "")
            if last_date == date_str:
                continue
            if mode == "monthly" and last_date.startswith(month_prefix):
                continue
            eligible.append(peer)
        eligible.sort(key=lambda peer: last_sent.get(peer["id"], ""))
        return eligible

    async def _send_wave(
        self, conn: Any, wave: list[dict], date_str: str, config: JumaRateConfig,
        custom_greetings: dict[str, str], deadline: datetime, fixed_now: Optional[datetime],
    ) -> dict:
        sent = failed = 0
        aborted: Optional[str] = None
        hit_deadline = False
        for idx, peer in enumerate(wave):
            if is_excluded_member(peer, config, excluded_names=settings.EXCLUDED_NAMES)[0]:
                continue
            loop_now = _as_tashkent(fixed_now) if fixed_now is not None else datetime.now(TASHKENT_TZ)
            if is_quiet_hours(loop_now, config):
                wait_q = seconds_until_quiet_ends(loop_now, config)
                if loop_now + timedelta(seconds=wait_q) >= deadline:
                    hit_deadline = True
                    break
                await asyncio.sleep(wait_q)
            if loop_now >= deadline:
                hit_deadline = True
                break
            text = pick_greeting_text(peer, custom_greetings, JUMA_TEMPLATES)
            silent = is_silent_send_time(loop_now, config)
            status, detail = await _deliver_one_message(
                self.client, peer, text, config, silent=silent
            )
            if status == "sent":
                await conn.execute("INSERT OR IGNORE INTO juma_sent_logs (user_id, run_date) VALUES (?, ?)", (peer["id"], date_str))
                await conn.commit()
                sent += 1
                logger.info("[JUMA] Sent %d/%d (uid=%s, silent=%s)", sent, len(wave), peer["id"], silent)
            elif status == "abort":
                aborted = detail
                break
            else:
                failed += 1
            if idx + 1 < len(wave):
                delay_sec, _ = next_delay_seconds(sent if status == "sent" else 1, config)
                if loop_now + timedelta(seconds=delay_sec) >= deadline:
                    hit_deadline = True
                    break
                await asyncio.sleep(delay_sec)
        return {"sent": sent, "failed": failed, "aborted": aborted, "hit_deadline": hit_deadline}

    async def send_greetings(
        self, date_str: str, source_message=None, *, now: Optional[datetime] = None
    ) -> dict:
        """Juma tabriklarini anti-spam tartibi va issiq/sovuq limiti bilan yuboradi."""
        current = _as_tashkent(now or datetime.now(TASHKENT_TZ))
        if not automatic_customer_send_allowed("juma", now=current):
            logger.warning("[JUMA] Direct send blocked outside Friday.")
            return {"sent": 0, "failed": 0, "deferred_cold": 0, "excluded": 0, "aborted": "not_friday", "hit_deadline": False}
        config = load_juma_rate_config()
        deadline = compute_juma_deadline(current, config)
        msg_json = os.getenv("JUMA_MESSAGES_JSON", "").strip()
        custom = load_custom_greetings(Path(msg_json) if msg_json else None)
        recipients, excluded = await self.collect_recipients(config)
        if not recipients and excluded == 0:
            logger.warning("[JUMA] TN7 guruhi aʼzolari topilmadi — qayta uriniladi.")
            await self._notify_owner("⚠️ Juma TN7: guruh aʼzolari olinmadi, keyingi siklda qayta uriniladi.")
            return {"sent": 0, "failed": 0, "deferred_cold": 0, "excluded": 0, "aborted": "no_recipients", "hit_deadline": False}
        conn = await self.db.get_connection()
        eligible = await self._filter_eligible_recipients(conn, recipients, date_str)
        wave, deferred = classify_and_order_recipients(eligible, cold_limit=config.cold_daily_limit)
        logger.info("[JUMA] Wave prepared: total=%d eligible=%d wave=%d deferred=%d excluded=%d", len(recipients), len(eligible), len(wave), len(deferred), excluded)
        if not wave:
            await self._mark_as_sent(date_str)
            await self._notify_owner("🕌 Juma tabrigi: bugun yuboriladigan yangi aʼzo qolmadi.")
            return {"sent": 0, "failed": 0, "deferred_cold": len(deferred), "excluded": excluded, "aborted": None, "hit_deadline": False}
        await self._notify_owner(f"▶️ Juma TN7 tabrigi boshlandi: toʻlqin={len(wave)}, blok={excluded}, keyingi={len(deferred)}")
        res = await self._send_wave(conn, wave, date_str, config, custom, deadline, now)
        await self._mark_as_sent(date_str)
        summary = (
            f"🛑 Juma tabrigi toʻxtatildi ({res['aborted']}): {res['sent']} yuborildi, {res['failed']} xato."
            if res["aborted"]
            else f"✅ Juma tabrigi yakunlandi: {res['sent']} yuborildi, {res['failed']} xato, {len(deferred)} keyingi Jumaga."
        )
        await self._notify_owner(summary)
        return {**res, "deferred_cold": len(deferred), "excluded": excluded}
