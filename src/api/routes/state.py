"""Shared state for api_server route modules.

Usage:
    from src.api.routes.state import api_state
    api_state.db_instance  # access the database
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class APIState:
    """Mutable shared state accessed by all route modules."""
    user_client: Any = None
    db_instance: Any = None
    msg_controller: Any = None
    action_parser: Any = None
    audit_agent: Any = None
    amocrm_instance: Any = None

    # Queues
    command_queue: Any = field(default_factory=asyncio.Queue)
    outgoing_messages: Any = field(default_factory=asyncio.Queue)

    # Telegram Business connections
    business_connections: Dict[str, Any] = field(default_factory=dict)
    _userbot_group_access_snapshot: Dict[str, Any] = field(default_factory=dict)
    _telegram_ai_ingress_status: Dict[str, Any] = field(default_factory=dict)

    # Health / caching
    cached_status: Dict[str, Any] = field(default_factory=dict)
    _health_db_snapshot_cache: Dict[str, Any] = field(default_factory=dict)
    _HEALTH_DB_TIMEOUT_SECONDS: float = 5.0

    # Heartbeat
    _last_heartbeat_at: Any = None
    _boot_at: Any = None
    _heartbeat_stale_seconds: int = 120

    # CRM audit
    cached_crm_audit: Dict[str, Any] = field(default_factory=dict)
    system_activities: Any = field(default_factory=list)
    legacy_runtime_inventory_cache: Any = None

    # AmoCRM backfill
    _call_backfill_task: Any = None
    _call_backfill_last_status: Dict[str, Any] = field(default_factory=dict)

    # Bot-to-bot
    _bot2bot_tracker: Dict[str, list] = field(default_factory=dict)
    BOT2BOT_MAX_ROUNDS: int = 3
    BOT2BOT_COOLDOWN_SEC: int = 300

    # AI analytics
    _quality_analyzer: Any = None
    _call_analytics: Any = None
    _ai_task_manager: Any = None
    _conversation_engine: Any = None


# Singleton — imported by all route modules
api_state = APIState()
