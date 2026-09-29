from src.services.core.contact_intro_parser import ContactIntro
from src.services.core.contact_intro_updates import propose_intro_update


def proposal(customers=None, receipts=(), **kwargs):
    return propose_intro_update(
        ContactIntro("Ali", "", "+998901234567", brand="Example"),
        customers if customers is not None else [
            {"id": "customer-1", "phone": "901234567", "telegram_user_id": 42}
        ], receipts, chat_id=-1001, message_id=2, sender_id=42,
        message_date="2026-09-27T09:00:00Z", **kwargs,
    )


def test_only_existing_unique_customer_with_verified_sender():
    assert proposal([]).status == "identity_review_required"
    row = {"id": "a", "phone": "901234567", "telegram_user_id": 42}
    assert proposal([row, dict(row, id="b")]).status == "identity_review_required"
    assert proposal([dict(row, phone="99890123456789")]).status == "identity_review_required"
    assert proposal([dict(row, telegram_user_id=99)]).status == "sender_review_required"
    assert proposal(forwarded=True).status == "source_review_required"


def test_fills_empty_fields_but_retains_conflicts():
    result = proposal([{"id": "a", "phone": "901234567", "telegram_user_id": 42,
                        "brand": "Existing"}])
    assert result.changes == {"first_name": "Ali"}
    assert result.conflicts["brand"]["current"] == "Existing"
    assert result.source["message_id"] == 2
    assert not result.airtable_eligible


def test_payment_requires_linked_confirmed_income_record():
    receipt = {"customer_id": "customer-1", "status": "confirmed",
               "kind": "income", "record_id": "receipt-1", "amount": "880000"}
    assert proposal(receipts=[receipt]).airtable_eligible
    for changes in ({"status": "promised"}, {"customer_id": "other"},
                    {"record_id": ""}, {"amount": "NaN"}, {"amount": -1},
                    {"kind": "expense"}, {"refunded": True}):
        assert not proposal(receipts=[dict(receipt, **changes)]).airtable_eligible


def test_reprocessing_same_values_is_unchanged():
    row = {"id": "a", "phone": "901234567", "telegram_user_id": 42,
           "first_name": "Ali", "brand": "Example"}
    assert proposal([row]).status == "unchanged"
