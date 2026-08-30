"""
Live Monitor — real-time userbot faoliyatini kuzatish uchun WebSocket dashboard.

Usage:
    # api_server.py ga qo'shish:
    from src.api.live_monitor import router as live_monitor_router
    app.include_router(live_monitor_router)

    # handle_new_message dan event yuborish:
    from src.api.live_monitor import broadcast_event
    await broadcast_event({"type": "message", "chat_id": 123, ...})
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.api.rbac import Permission, require_permissions
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["live-monitor"],
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)

# ---------------------------------------------------------------------------
# Event bus — broadcasters and history
# ---------------------------------------------------------------------------

_connections: Set[WebSocket] = set()
_event_history: deque = deque(maxlen=500)  # oxirgi 500 ta event
_stats: Dict[str, Any] = {
    "start_time": time.time(),
    "total_messages": 0,
    "total_commands": 0,
    "total_errors": 0,
    "total_replies": 0,
    "active_chats": set(),
    "last_message_at": None,
}


async def broadcast_event(event: Dict[str, Any]) -> None:
    """Barcha ulangan WebSocket clientlarga event yuborish."""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    _event_history.append(event)

    # Stats yangilash
    event_type = event.get("type", "")
    if event_type == "message":
        _stats["total_messages"] += 1
        _stats["last_message_at"] = event["timestamp"]
        chat_id = event.get("chat_id")
        if chat_id:
            _stats["active_chats"].add(chat_id)
    elif event_type == "command":
        _stats["total_commands"] += 1
    elif event_type == "error":
        _stats["total_errors"] += 1
    elif event_type == "reply":
        _stats["total_replies"] += 1

    # Broadcast
    if not _connections:
        return

    message = json.dumps(event, default=str)
    disconnected: List[WebSocket] = []
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            disconnected.append(ws)
    for ws in disconnected:
        _connections.discard(ws)


def get_stats() -> Dict[str, Any]:
    """Hozirgi statistikani qaytarish."""
    uptime = time.time() - _stats["start_time"]
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    return {
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": int(uptime),
        "total_messages": _stats["total_messages"],
        "total_commands": _stats["total_commands"],
        "total_errors": _stats["total_errors"],
        "total_replies": _stats["total_replies"],
        "active_chats": len(_stats["active_chats"]),
        "last_message_at": _stats["last_message_at"],
        "connected_clients": len(_connections),
    }


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Oxirgi eventlarni qaytarish."""
    return list(_event_history)[-limit:]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """Real-time event stream uchun WebSocket endpoint."""
    await websocket.accept()
    _connections.add(websocket)
    logger.info("[LIVE-MONITOR] Client ulandi: %d ta client", len(_connections))

    try:
        # Stats yuborish
        await websocket.send_text(json.dumps({
            "type": "connected",
            "stats": get_stats(),
            "history": get_recent_events(20),
        }, default=str))

        # Client dan xabar kutish (heartbeat yoki buyruq)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg.get("type") == "get_stats":
                    await websocket.send_text(json.dumps({
                        "type": "stats",
                        "stats": get_stats(),
                    }, default=str))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(websocket)
        logger.info("[LIVE-MONITOR] Client uzildi: %d ta client qoldi", len(_connections))


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get("/api/live/stats")
async def api_live_stats() -> Dict[str, Any]:
    """Statistikani REST orqali olish."""
    return get_stats()


@router.get("/api/live/events")
async def api_live_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Oxirgi eventlarni REST orqali olish."""
    return get_recent_events(limit)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

from src.api.live_monitor_template import DASHBOARD_HTML


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_dashboard() -> HTMLResponse:
    """Web dashboard sahifasi."""
    return HTMLResponse(content=DASHBOARD_HTML)
