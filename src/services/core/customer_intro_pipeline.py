"""Apply verified Telegram customer-intro proposals through injected adapters.

This module deliberately contains no vendor-specific discovery.  Callers provide
the current customer/payment snapshots and adapters for the external writes.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from src.services.core.contact_intro_parser import ContactIntro, parse_contact_intro
from src.services.core.contact_intro_updates import IntroUpdateProposal, propose_intro_update


class IntroWriter(Protocol):
    def update_amocrm(self, customer_id: str, changes: Mapping[str, str], source: Mapping[str, Any]) -> None: ...
    def update_airtable(self, customer_id: str, changes: Mapping[str, str], source: Mapping[str, Any]) -> None: ...
    def append_obsidian(self, customer_id: str, intro: ContactIntro, source: Mapping[str, Any]) -> None: ...


class IdempotencyStore(Protocol):
    def seen(self, key: str) -> bool: ...
    def mark(self, key: str) -> None: ...


@dataclass
class IntroPipelineResult:
    status: str
    proposal: IntroUpdateProposal | None = None
    writes: list[str] = field(default_factory=list)


def process_intro_message(
    text: str,
    *,
    source_chat: str,
    chat_id: int,
    message_id: int,
    sender_id: int,
    message_date: str,
    customers: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    writer: IntroWriter,
    idempotency: IdempotencyStore,
    forwarded: bool = False,
) -> IntroPipelineResult:
    """Parse and apply one intro message, safely and idempotently."""
    intro = parse_contact_intro(text, source_chat=source_chat)
    if intro is None:
        return IntroPipelineResult("not_an_intro")
    key = f"telegram-intro:{chat_id}:{message_id}"
    if idempotency.seen(key):
        return IntroPipelineResult("duplicate")
    proposal = propose_intro_update(
        intro, customers, receipts, chat_id=chat_id, message_id=message_id,
        sender_id=sender_id, message_date=message_date, forwarded=forwarded,
    )
    if proposal.status not in {"ready", "unchanged"}:
        return IntroPipelineResult(proposal.status, proposal)
    source = proposal.source
    if proposal.changes:
        writer.update_amocrm(proposal.customer_id, proposal.changes, source)
    writer.append_obsidian(proposal.customer_id, intro, source)
    if proposal.airtable_eligible and proposal.changes:
        writer.update_airtable(proposal.customer_id, proposal.changes, source)
    idempotency.mark(key)
    writes = ["obsidian"]
    if proposal.changes:
        writes.append("amocrm")
    if proposal.airtable_eligible and proposal.changes:
        writes.append("airtable")
    return IntroPipelineResult(proposal.status, proposal, writes)
