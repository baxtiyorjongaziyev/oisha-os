from __future__ import annotations

import html
import json
from typing import Any

from .batch import BATCH_TOOL
from .models import PendingOperation


SENSITIVE_KEYS = frozenset(
    {
        "api_hash",
        "authorization",
        "bot_token",
        "password",
        "secret",
        "session",
        "session_string",
        "token",
    }
)


def _redacted(value: Any, key: str = "") -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redacted(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redacted(item) for item in value[:20]]
    if isinstance(value, str):
        return value[:200]
    return value


def safe_arguments_preview(arguments: dict[str, Any]) -> str:
    return json.dumps(
        _redacted(arguments), ensure_ascii=False, sort_keys=True, indent=2
    )[:900]


def batch_actions_preview(arguments: dict[str, Any], budget: int = 3000) -> str:
    """Every queued action on its own line, so the owner sees the whole batch."""
    lines: list[str] = []
    used = 0
    actions = arguments.get("actions") or []
    for index, action in enumerate(actions, 1):
        args = json.dumps(
            _redacted(action.get("arguments") or {}), ensure_ascii=False, sort_keys=True
        )
        line = f"{index}. {action.get('tool', '?')} {args[:140]}"
        used += len(line) + 1
        if used > budget:
            lines.append(f"... yana {len(actions) - index + 1} ta amal koʻrsatilmadi")
            break
        lines.append(line)
    return "\n".join(lines)


def build_approval_card(operation: PendingOperation) -> tuple[str, dict[str, Any]]:
    if operation.tool_name == BATCH_TOOL:
        count = len(operation.arguments.get("actions") or [])
        body = (
            f"📦 <b>Paket tasdiq: {count} ta amal</b>\n\n"
            f"<b>Soʻrovchi:</b> {html.escape(operation.requester)}\n"
            f"<b>Muddati:</b> {operation.expires_at.isoformat()}\n\n"
            f"<pre>{html.escape(batch_actions_preview(operation.arguments))}</pre>"
        )
        return body, _approval_keyboard(operation)
    warning = (
        "⚠️ <b>O‘CHIRISH/BLOKLASH AMALI</b>\n"
        if operation.risk == "destructive"
        else "✍️ <b>Telegram o‘zgarishi tasdiq kutmoqda</b>\n"
    )
    text = (
        f"{warning}\n"
        f"<b>Amal:</b> <code>{html.escape(operation.tool_name)}</code>\n"
        f"<b>So‘rovchi:</b> {html.escape(operation.requester)}\n"
        f"<b>Muddati:</b> {operation.expires_at.isoformat()}\n\n"
        f"<pre>{html.escape(safe_arguments_preview(operation.arguments))}</pre>"
    )
    return text, _approval_keyboard(operation)


def _approval_keyboard(operation: PendingOperation) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Tasdiqlash",
                    "callback_data": f"mcp:approve:{operation.id}",
                },
                {
                    "text": "❌ Bekor qilish",
                    "callback_data": f"mcp:cancel:{operation.id}",
                },
            ]
        ]
    }


class TelegramApprovalNotifier:
    def __init__(self, bot_token: str, owner_id: int):
        if not bot_token or not owner_id:
            raise ValueError("BOT_TOKEN and OWNER_ID are required for MCP approvals")
        self.bot_token = bot_token
        self.owner_id = int(owner_id)

    async def notify(self, operation: PendingOperation) -> None:
        import httpx

        text, keyboard = build_approval_card(operation)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.owner_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
