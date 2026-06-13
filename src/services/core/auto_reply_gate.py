"""
Auto-reply tiered rollout gate.

Controls whether an inbound message should be auto-replied, sent to shadow
review, or ignored entirely. Three inputs:

  1. AUTO_REPLY_MODE (env var, overridable via DB flag `auto_reply_mode`):
       - "off"      : nothing auto-replies; only explicit @mentions
       - "shadow"   : bot drafts a reply, posts to admin preview, waits for approval
       - "vip_only" : bot auto-sends for lead_score >= VIP threshold; rest go to shadow
       - "live"     : bot auto-sends for every matching message

  2. Kill switch DB flag `auto_reply_live` — when False, force-downgrades to "off"
     regardless of mode. Flipped by admin via /pause_auto and /resume_auto.
     This is deliberately a SECOND layer on top of mode so an Owner can kill
     the bot during a crisis without touching env vars.

  3. Per-message context (lead_score, is_mentioned, confidence, triggers).

Decision is packaged as a Decision dataclass so the caller can log/audit
rather than just branching on a bool.

Why both mode AND kill-switch? Mode is a *policy* (shadow → vip_only → live
as trust grows). Kill-switch is an *incident handle* (something's off, pull
the cord NOW). Two orthogonal axes, two knobs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

# Escalation triggers — if the user message contains any of these, the bot
# must NOT auto-reply and instead escalate to the Owner. Matched case-insensitive.
ESCALATION_TRIGGERS = (
    "shikoyat",  # complaint
    "qaytarish",  # refund
    "advokat",  # lawyer
    "sud",  # court
    "vaqtida bermadi",  # did not deliver on time
    "aldadi",  # cheated
    "firibgar",  # fraud
    "qaytarib bering",  # give back
)

VALID_MODES = ("off", "shadow", "vip_only", "live", "auto")

# DB flag keys
FLAG_KILL_SWITCH = "auto_reply_live"  # bool, True=allowed, False=killed
FLAG_MODE = "auto_reply_mode"  # str, one of VALID_MODES (overrides env)


@dataclass
class Decision:
    """Result of a gate evaluation."""

    action: str  # "send" | "shadow" | "skip" | "escalate"
    reason: str  # human-readable explanation (shown in logs/admin)
    effective_mode: str  # which mode was actually applied after overrides
    kill_switch_on: bool  # True if kill-switch is pulled (forces "skip")


async def _load_mode(db: Any) -> str:
    """DB override wins; else env; else 'off' (safe default)."""
    if db is not None:
        try:
            stored = await db.get_state(FLAG_MODE)
            if stored and str(stored).lower() in VALID_MODES:
                return str(stored).lower()
        except Exception:
            pass
    env = os.environ.get("AUTO_REPLY_MODE", "off").strip().lower()
    return env if env in VALID_MODES else "off"


async def _load_kill_switch(db: Any) -> bool:
    """Kill-switch is True (live) by default; admin flips to False via /pause_auto."""
    if db is None:
        return True
    try:
        stored = await db.get_state(FLAG_KILL_SWITCH)
        if stored is None:
            return True
        return str(stored).lower() not in ("0", "false", "off", "no")
    except Exception:
        return True


async def _load_scoped_kill_switch(
    db: Any,
    module: str = "",
    client_id: str = "",
) -> bool:
    if db is None:
        return False
    keys = ["erp:kill_switch:global"]
    if module:
        keys.append(f"erp:kill_switch:module:{module}")
    if client_id:
        keys.append(f"erp:kill_switch:client:{client_id}")
    for key in keys:
        try:
            value = await db.get_state(key, "false")
        except TypeError:
            value = await db.get_state(key)
        if str(value or "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


def _has_escalation_trigger(text: str) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for trigger in ESCALATION_TRIGGERS:
        if trigger in lowered:
            return trigger
    return None


def _vip_threshold() -> int:
    try:
        return int(os.environ.get("VIP_LEAD_SCORE_THRESHOLD", "80"))
    except ValueError:
        return 80


async def evaluate(
    db: Any,
    *,
    is_mentioned: bool = False,
    lead_score: int = 0,
    message_text: str = "",
    confidence: Optional[float] = None,
    module: str = "telegram",
    client_id: str = "",
) -> Decision:
    """Decide what to do with an inbound message.

    Args:
        db: Database instance with `get_state(key)` support.
        is_mentioned: True if the bot/owner was @-mentioned — bypasses mode
            gating (Owner always wants to hear back when directly called out).
        lead_score: 0-100 quality score for the conversation. Used by the
            vip_only tier to decide whether to auto-send.
        message_text: the user's raw text; scanned for escalation triggers.
        confidence: optional bot reply confidence 0-1. If < 0.6 we shadow
            even in live mode (safety net).

    Returns:
        Decision(action, reason, effective_mode, kill_switch_on).
    """
    mode = await _load_mode(db)
    kill_on = (not await _load_kill_switch(db)) or await _load_scoped_kill_switch(
        db, module=module, client_id=client_id
    )

    # "off" mode — no replies at all, including @mentions.
    if mode == "off":
        return Decision(
            action="skip",
            reason="mode_off",
            effective_mode="off",
            kill_switch_on=kill_on,
        )

    # Escalation triggers win over every mode.
    trigger = _has_escalation_trigger(message_text)
    if trigger:
        return Decision(
            action="escalate",
            reason=f"trigger:{trigger}",
            effective_mode=mode,
            kill_switch_on=kill_on,
        )

    # Kill switch forces "off".
    if kill_on:
        return Decision(
            action="skip",
            reason="kill_switch_active",
            effective_mode="off",
            kill_switch_on=True,
        )

    # Mention short-circuits to send only while every kill-switch is clear.
    if is_mentioned:
        return Decision(
            action="send",
            reason="mention_override",
            effective_mode=mode,
            kill_switch_on=kill_on,
        )

    # Low-confidence always shadows, regardless of mode (except off).
    if confidence is not None and confidence < 0.6 and mode in ("vip_only", "live"):
        return Decision(
            action="shadow",
            reason=f"low_confidence({confidence:.2f})",
            effective_mode=mode,
            kill_switch_on=kill_on,
        )

    if mode == "off":
        return Decision(
            action="skip",
            reason="mode_off",
            effective_mode="off",
            kill_switch_on=kill_on,
        )
    if mode == "shadow":
        return Decision(
            action="shadow",
            reason="tier1_shadow",
            effective_mode="shadow",
            kill_switch_on=kill_on,
        )
    if mode == "vip_only":
        threshold = _vip_threshold()
        if lead_score >= threshold:
            return Decision(
                action="send",
                reason=f"vip_lead({lead_score}>={threshold})",
                effective_mode="vip_only",
                kill_switch_on=kill_on,
            )
        return Decision(
            action="shadow",
            reason=f"non_vip({lead_score}<{threshold})",
            effective_mode="vip_only",
            kill_switch_on=kill_on,
        )
    # live
    if mode == "live":
        return Decision(
            action="send",
            reason="tier3_live",
            effective_mode="live",
            kill_switch_on=kill_on,
        )
    # auto — Telegram Chat Automation mode: bot is connected to owner's profile,
    # replies on behalf of the owner in ALL chats without score threshold.
    # Only active when user explicitly connects the bot via Telegram settings.
    return Decision(
        action="send",
        reason="tier4_auto_chat_automation",
        effective_mode="auto",
        kill_switch_on=kill_on,
    )
