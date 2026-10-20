"""Shared inbound policy: public intake stays open, private commands need pairing.

Pairing approval is owner-side only via PairingSecurityGate.approve_pairing;
the challenge is never sent to or auto-approved for an untrusted sender.
"""
from __future__ import annotations

from src.services.core.telegram.pairing_security_gate import GateDecision, PairingSecurityGate

inbound_gate = PairingSecurityGate()


def evaluate_message(sender_id: int | None, text: str, *, is_private: bool, owner_id: int) -> GateDecision:
    if owner_id:
        inbound_gate.trusted_senders = {str(owner_id)}
    else:
        inbound_gate.trusted_senders = set()
    return inbound_gate.evaluate_inbound(
        str(sender_id), text,
        requires_pairing=is_private and text.lstrip().startswith("/"),
    )


def build_telethon_guard(owner_id: int):
    """Register this callback first, ahead of every inbound tool handler."""
    async def guard(event):
        from telethon.events import StopPropagation

        decision = evaluate_message(
            event.sender_id, event.raw_text or "", is_private=event.is_private,
            owner_id=owner_id,
        )
        if not decision.allowed:
            raise StopPropagation
    return guard
