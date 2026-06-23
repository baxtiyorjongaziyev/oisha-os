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
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live-monitor"])

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

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oisha-OS Live Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #2a2a4a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            color: #a78bfa;
        }
        .status-badge {
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }
        .status-online { background: #065f46; color: #34d399; }
        .status-offline { background: #7f1d1d; color: #fca5a5; }
        .status-connecting { background: #78350f; color: #fbbf24; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            padding: 20px 30px;
        }
        .stat-card {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
        }
        .stat-card .label {
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .value {
            font-size: 28px;
            font-weight: 700;
            color: #a78bfa;
            margin-top: 4px;
        }
        .stat-card .sub {
            font-size: 11px;
            color: #4b5563;
            margin-top: 2px;
        }

        .main-content {
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 20px;
            padding: 0 30px 30px;
            height: calc(100vh - 200px);
        }

        .event-feed {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .event-feed-header {
            padding: 14px 18px;
            border-bottom: 1px solid #1f2937;
            font-weight: 600;
            color: #9ca3af;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .event-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }
        .event-item {
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 4px;
            font-size: 13px;
            line-height: 1.5;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .event-message { background: #0c1a2e; border-left: 3px solid #3b82f6; }
        .event-command { background: #1a1a0c; border-left: 3px solid #eab308; }
        .event-reply { background: #0c2e1a; border-left: 3px solid #22c55e; }
        .event-error { background: #2e0c0c; border-left: 3px solid #ef4444; }
        .event-system { background: #1a1a2e; border-left: 3px solid #a78bfa; }
        .event-voice { background: #2e1a0c; border-left: 3px solid #f97316; }
        .event-sync { background: #0c2e2e; border-left: 3px solid #06b6d4; }

        .event-time {
            font-size: 11px;
            color: #4b5563;
            font-family: monospace;
        }
        .event-type {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 6px;
        }
        .type-message { background: #1e3a5f; color: #60a5fa; }
        .type-command { background: #3b3509; color: #facc15; }
        .type-reply { background: #0f3d20; color: #4ade80; }
        .type-error { background: #3d0f0f; color: #f87171; }
        .type-system { background: #2e1f4e; color: #c084fc; }
        .type-voice { background: #3d2a0f; color: #fb923c; }
        .type-sync { background: #0f3d3d; color: #22d3ee; }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .sidebar-card {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
        }
        .sidebar-card h3 {
            font-size: 13px;
            color: #9ca3af;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .chat-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #1f2937;
            font-size: 13px;
        }
        .chat-item:last-child { border-bottom: none; }
        .chat-count {
            background: #1f2937;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            color: #a78bfa;
        }

        .filter-bar {
            padding: 8px 14px;
            border-bottom: 1px solid #1f2937;
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #2a2a4a;
            background: transparent;
            color: #6b7280;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .filter-btn:hover { border-color: #a78bfa; color: #a78bfa; }
        .filter-btn.active { background: #a78bfa; color: #0a0a0f; border-color: #a78bfa; }

        .no-events {
            text-align: center;
            padding: 40px;
            color: #4b5563;
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>👸 Oisha-OS Live Monitor</h1>
        <div id="status" class="status-badge status-connecting">Ulanyapti...</div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Uptime</div>
            <div class="value" id="uptime">--</div>
        </div>
        <div class="stat-card">
            <div class="label">Xabarlar</div>
            <div class="value" id="total-messages">0</div>
            <div class="sub" id="last-message">--</div>
        </div>
        <div class="stat-card">
            <div class="label">Buyruqlar</div>
            <div class="value" id="total-commands">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Javoblar</div>
            <div class="value" id="total-replies">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Xatoliklar</div>
            <div class="value" id="total-errors">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Aktiv chatlar</div>
            <div class="value" id="active-chats">0</div>
        </div>
    </div>

    <div class="main-content">
        <div class="event-feed">
            <div class="event-feed-header">
                <span>Live Event Feed</span>
                <span id="event-count">0 events</span>
            </div>
            <div class="filter-bar">
                <button class="filter-btn active" data-filter="all">Barchasi</button>
                <button class="filter-btn" data-filter="message">Xabarlar</button>
                <button class="filter-btn" data-filter="command">Buyruqlar</button>
                <button class="filter-btn" data-filter="reply">Javoblar</button>
                <button class="filter-btn" data-filter="voice">Ovoz</button>
                <button class="filter-btn" data-filter="error">Xatoliklar</button>
                <button class="filter-btn" data-filter="sync">Sinxro</button>
            </div>
            <div class="event-list" id="event-list">
                <div class="no-events">Eventlar kutyapti...</div>
            </div>
        </div>

        <div class="sidebar">
            <div class="sidebar-card">
                <h3>Ulangan clientlar</h3>
                <div id="connected-clients" style="font-size:24px;color:#a78bfa;">0</div>
            </div>
            <div class="sidebar-card">
                <h3>Oxirgi xabarlar</h3>
                <div id="recent-chats"></div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let events = [];
        let activeFilter = 'all';
        let reconnectTimer = null;

        function connect() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${location.host}/ws/live`);

            ws.onopen = () => {
                document.getElementById('status').className = 'status-badge status-online';
                document.getElementById('status').textContent = 'Ulangan';
            };

            ws.onclose = () => {
                document.getElementById('status').className = 'status-badge status-offline';
                document.getElementById('status').textContent = 'Uzildi';
                reconnectTimer = setTimeout(connect, 3000);
            };

            ws.onerror = () => {
                document.getElementById('status').className = 'status-badge status-offline';
                document.getElementById('status').textContent = 'Xatolik';
            };

            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'connected') {
                    updateStats(data.stats);
                    if (data.history) {
                        data.history.forEach(ev => addEvent(ev, false));
                    }
                } else if (data.type === 'stats') {
                    updateStats(data.stats);
                } else if (data.type === 'pong') {
                    // heartbeat
                } else {
                    addEvent(data, true);
                }
            };
        }

        function updateStats(stats) {
            document.getElementById('uptime').textContent = stats.uptime || '--';
            document.getElementById('total-messages').textContent = stats.total_messages || 0;
            document.getElementById('total-commands').textContent = stats.total_commands || 0;
            document.getElementById('total-replies').textContent = stats.total_replies || 0;
            document.getElementById('total-errors').textContent = stats.total_errors || 0;
            document.getElementById('active-chats').textContent = stats.active_chats || 0;
            document.getElementById('connected-clients').textContent = stats.connected_clients || 0;
            if (stats.last_message_at) {
                const d = new Date(stats.last_message_at);
                document.getElementById('last-message').textContent = 'Oxirgi: ' + d.toLocaleTimeString();
            }
        }

        function addEvent(ev, scroll) {
            if (activeFilter !== 'all' && ev.type !== activeFilter) return;

            const list = document.getElementById('event-list');
            const noEvents = list.querySelector('.no-events');
            if (noEvents) noEvents.remove();

            const div = document.createElement('div');
            div.className = `event-item event-${ev.type || 'system'}`;

            const time = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '';
            const typeLabel = ev.type || 'system';
            const text = ev.text || ev.message || ev.error || JSON.stringify(ev).slice(0, 200);

            div.innerHTML = `
                <span class="event-time">${time}</span>
                <span class="event-type type-${typeLabel}">${typeLabel}</span>
                ${escapeHtml(text)}
            `;

            list.appendChild(div);
            events.push(ev);

            // Limit
            while (list.children.length > 200) {
                list.removeChild(list.firstChild);
            }

            document.getElementById('event-count').textContent = `${events.length} events`;

            if (scroll !== false) {
                list.scrollTop = list.scrollHeight;
            }
        }

        function escapeHtml(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        // Filters
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeFilter = btn.dataset.filter;
                // Re-render
                const list = document.getElementById('event-list');
                list.innerHTML = '';
                events.forEach(ev => addEvent(ev, false));
                if (events.length === 0) {
                    list.innerHTML = '<div class="no-events">Eventlar kutyapti...</div>';
                }
            });
        });

        // Heartbeat
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000);

        connect();
    </script>
</body>
</html>"""


@router.get("/live", response_class=HTMLResponse)
async def live_dashboard() -> str:
    """Live monitor dashboard sahifasi."""
    return DASHBOARD_HTML
