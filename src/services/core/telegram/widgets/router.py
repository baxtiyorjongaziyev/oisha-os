"""Routes ``widget_query`` updates to module handlers and answers them.

Widget buttons send ``<module>:<action>[:<arg>]`` (<= 64 bytes). Every query
must be answered within 15 seconds, so handlers get a shorter budget and a
fallback answer is sent on timeout or error.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from src.services.core.telegram.widgets.client import WidgetClient

logger = logging.getLogger("WidgetQueryRouter")

WIDGET_UPDATE_KEYS = ("widget_query", "shared_widget_query")
HANDLER_TIMEOUT_SECONDS = 12.0
DENIED_ANSWER = "Ruxsat yoʻq"
TIMEOUT_ANSWER = "Qabul qilindi, natija keyinroq chiqadi"
ERROR_ANSWER = "Xatolik yuz berdi"
UNKNOWN_ANSWER = "Nomaʼlum amal"


@dataclass(frozen=True)
class WidgetQuery:
    id: str
    user_id: Optional[int]
    data: str
    module: str
    action: str
    arg: str
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    inline_message_id: Optional[str] = None
    widget_id: Optional[str] = None
    shared: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


WidgetHandler = Callable[[WidgetQuery], Awaitable[Optional[str]]]
Authorizer = Callable[[WidgetQuery], Awaitable[bool]]


def parse_widget_update(update: Dict[str, Any]) -> Optional[WidgetQuery]:
    for key in WIDGET_UPDATE_KEYS:
        q = update.get(key)
        if not isinstance(q, dict) or not q.get("id"):
            continue
        data = str(q.get("data") or "")
        parts = data.split(":", 2)
        return WidgetQuery(
            id=str(q["id"]),
            user_id=(q.get("from") or {}).get("id"),
            data=data,
            module=parts[0].strip().lower() if parts and parts[0] else "",
            action=parts[1].strip().lower() if len(parts) > 1 else "",
            arg=parts[2] if len(parts) > 2 else "",
            chat_id=(q.get("chat") or {}).get("id"),
            message_id=q.get("message_id"),
            inline_message_id=q.get("inline_message_id"),
            widget_id=q.get("widget_id"),
            shared=key == "shared_widget_query",
            raw=q,
        )
    return None


class WidgetQueryRouter:
    def __init__(
        self,
        client: WidgetClient,
        *,
        allowed_user_ids: Iterable[int] = (),
        authorizer: Optional[Authorizer] = None,
        timeout: float = HANDLER_TIMEOUT_SECONDS,
    ):
        self.client = client
        self.allowed_user_ids = {int(u) for u in allowed_user_ids if u}
        self.authorizer = authorizer
        self.timeout = timeout
        self._handlers: Dict[str, WidgetHandler] = {}

    def register(self, module: str, handler: WidgetHandler) -> None:
        self._handlers[module.strip().lower()] = handler

    async def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        query = parse_widget_update(update)
        if query is None:
            return {"handled": False, "reason": "not_widget_query"}

        answer, reason = await self._resolve(query)
        try:
            await self.client.answer_widget_query(query.id, data=answer)
        except Exception as exc:  # noqa: BLE001 - answering must never crash polling
            logger.warning("[WIDGET] answerWidgetQuery failed: %s", type(exc).__name__)
            return {"handled": True, "answered": False, "reason": reason, "module": query.module}
        return {"handled": True, "answered": True, "reason": reason, "module": query.module}

    async def _resolve(self, query: WidgetQuery) -> tuple[Optional[str], str]:
        if self.allowed_user_ids and query.user_id not in self.allowed_user_ids:
            return DENIED_ANSWER, "user_not_allowed"
        if self.authorizer is not None:
            try:
                if not await self.authorizer(query):
                    return DENIED_ANSWER, "policy_denied"
            except Exception:  # noqa: BLE001
                logger.exception("[WIDGET] authorizer failed")
                return DENIED_ANSWER, "policy_error"

        handler = self._handlers.get(query.module)
        if handler is None:
            return UNKNOWN_ANSWER, "unknown_module"
        try:
            return await asyncio.wait_for(handler(query), timeout=self.timeout), "ok"
        except asyncio.TimeoutError:
            return TIMEOUT_ANSWER, "timeout"
        except Exception:  # noqa: BLE001
            logger.exception("[WIDGET] handler %s failed", query.module)
            return ERROR_ANSWER, "handler_error"
