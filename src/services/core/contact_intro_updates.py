"""Build conservative update proposals; never mutate external systems here."""

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src.services.core.contact_intro_parser import ContactIntro


PROFILE_FIELDS = (
    "first_name", "last_name", "telegram", "instagram", "birthday",
    "birthplace", "brand", "activity", "region", "position",
)


def exact_phone(value: str) -> str:
    digits = "".join(c for c in str(value) if c.isascii() and c.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return digits if len(digits) == 12 and digits.startswith("998") else ""


@dataclass
class IntroUpdateProposal:
    status: str
    customer_id: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    changes: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, dict[str, str]] = field(default_factory=dict)
    airtable_eligible: bool = False


def confirmed_payment(customer_id: str, receipts: Sequence[Mapping]) -> bool:
    for receipt in receipts:
        if str(receipt.get("customer_id", "")) != customer_id:
            continue
        if receipt.get("status") != "confirmed" or not receipt.get("record_id"):
            continue
        if receipt.get("kind") != "income" or receipt.get("refunded"):
            continue
        try:
            amount = Decimal(str(receipt.get("amount", 0)))
            if amount.is_finite() and amount > 0:
                return True
        except (InvalidOperation, ValueError):
            continue
    return False


def propose_intro_update(
    intro: ContactIntro,
    customers: Sequence[Mapping],
    receipts: Sequence[Mapping],
    *,
    chat_id: int,
    message_id: int,
    sender_id: int,
    message_date: str,
    forwarded: bool = False,
) -> IntroUpdateProposal:
    """Match existing customers by exact phone and require sender verification.

    New facts fill empty fields. Different nonempty values require review rather
    than silently replacing staff-entered or previously verified information.
    """
    source = dict(chat_id=chat_id, message_id=message_id,
                  sender_id=sender_id, date=message_date)
    if forwarded or not message_id or not sender_id or not message_date:
        return IntroUpdateProposal("source_review_required", source=source)
    phone = exact_phone(intro.phone)
    matches = [c for c in customers if phone and exact_phone(c.get("phone", "")) == phone]
    if len(matches) != 1 or not matches[0].get("id"):
        return IntroUpdateProposal("identity_review_required", source=source)
    customer = matches[0]
    customer_id = str(customer["id"])
    if str(customer.get("telegram_user_id", "")) != str(sender_id):
        return IntroUpdateProposal("sender_review_required", customer_id, source)
    proposal = IntroUpdateProposal("ready", customer_id, source)
    values = asdict(intro)
    for key in PROFILE_FIELDS:
        incoming = str(values.get(key, "") or "").strip()
        current = str(customer.get(key, "") or "").strip()
        if not incoming or incoming == current:
            continue
        if current:
            proposal.conflicts[key] = {"current": current, "incoming": incoming}
        else:
            proposal.changes[key] = incoming
    proposal.airtable_eligible = confirmed_payment(customer_id, receipts)
    if not proposal.changes and not proposal.conflicts:
        proposal.status = "unchanged"
    return proposal
