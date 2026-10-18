"""
OpenClaw-Style Pairing & DM Security Gate for Telegram / Messaging
Protects agent from unauthorized tool triggers, prompt injection, and abuse.
"""

from __future__ import annotations

import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple
import structlog

logger = structlog.get_logger("PairingSecurityGate")

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"system\s*prompt\s*reveal",
    r"output\s+your\s+initial\s+instructions",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[SYSTEM_PROMPT\]",
]

COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    challenge_code: Optional[str] = None
    sanitized_text: str = ""


class PairingSecurityGate:
    """Controls access to AI agent capabilities from unknown inbound senders."""

    def __init__(
        self,
        max_requests_per_minute: int = 10,
        pairing_code_ttl: int = 600,
        trusted_senders: Optional[Set[str]] = None,
    ):
        self.max_rpm = max_requests_per_minute
        self.pairing_ttl = pairing_code_ttl
        self.trusted_senders: Set[str] = trusted_senders or set()
        self.paired_senders: Set[str] = set()
        self.pending_challenges: Dict[str, Tuple[str, float]] = {}  # sender_id -> (code, expires_at)
        self.sender_history: Dict[str, deque] = defaultdict(deque)

    def is_prompt_injection(self, text: str) -> bool:
        """Inspects message for jailbreak or prompt extraction attempts."""
        cleaned = text.strip()
        for pattern in COMPILED_INJECTION:
            if pattern.search(cleaned):
                return True
        return False

    def check_rate_limit(self, sender_id: str, now: Optional[float] = None) -> bool:
        """Enforces sliding-window rate limit per sender."""
        now = time.time() if now is None else now
        history = self.sender_history[sender_id]
        while history and now - history[0] > 60:
            history.popleft()
        if len(history) >= self.max_rpm:
            return False
        history.append(now)
        return True

    def generate_pairing_code(self, sender_id: str) -> str:
        """Generates a secure numeric pairing code (OpenClaw style)."""
        code = f"{secrets.randbelow(900000) + 100000}"
        self.pending_challenges[sender_id] = (code, time.time() + self.pairing_ttl)
        return code

    def approve_pairing(self, sender_id: str, code: str) -> bool:
        """Verifies pairing challenge and adds sender to approved whitelist."""
        record = self.pending_challenges.get(sender_id)
        if not record:
            return False
        expected_code, expires_at = record
        if time.time() > expires_at:
            self.pending_challenges.pop(sender_id, None)
            return False
        if code.strip() == expected_code:
            self.paired_senders.add(sender_id)
            self.pending_challenges.pop(sender_id, None)
            logger.info("Sender successfully paired", sender_id=sender_id)
            return True
        return False

    def evaluate_inbound(self, sender_id: str, text: str, requires_pairing: bool = False) -> GateDecision:
        """Evaluates whether an inbound message is safe to process by AI agent."""
        sender_str = str(sender_id)

        # 1. Rate limiting check
        if not self.check_rate_limit(sender_str):
            logger.warning("Rate limit exceeded", sender_id=sender_str)
            return GateDecision(allowed=False, reason="RATE_LIMITED")

        # 2. Prompt injection defense
        if self.is_prompt_injection(text):
            logger.warning("Prompt injection blocked", sender_id=sender_str, snippet=text[:60])
            return GateDecision(allowed=False, reason="PROMPT_INJECTION_DETECTED")

        # 3. Pairing verification (if channel is in pairing-enforced mode)
        if requires_pairing and sender_str not in self.trusted_senders and sender_str not in self.paired_senders:
            challenge = self.generate_pairing_code(sender_str)
            logger.info("Sender pairing challenged", sender_id=sender_str, challenge=challenge)
            return GateDecision(
                allowed=False,
                reason="PAIRING_REQUIRED",
                challenge_code=challenge,
            )

        return GateDecision(allowed=True, reason="ALLOWED", sanitized_text=text.strip())
