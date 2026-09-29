from src.services.core.customer_intro_pipeline import process_intro_message


class Store:
    def __init__(self): self.keys = set()
    def seen(self, key): return key in self.keys
    def mark(self, key): self.keys.add(key)


class Writer:
    def __init__(self): self.calls = []
    def update_amocrm(self, *args): self.calls.append(("amocrm", args))
    def update_airtable(self, *args): self.calls.append(("airtable", args))
    def append_obsidian(self, *args): self.calls.append(("obsidian", args))


TEXT = """Ism: Ali
Telefon: +998 90 123 45 67
Brend: Example
Faoliyat turi: Dizayn
Hudud: Toshkent
Telegram: @ali_example
"""


def run(writer, store, receipts=()):
    return process_intro_message(
        TEXT, source_chat="TN6", chat_id=-100, message_id=7, sender_id=42,
        message_date="2026-09-27T10:00:00Z",
        customers=[{"id": "c1", "phone": "901234567", "telegram_user_id": 42}],
        receipts=receipts, writer=writer, idempotency=store,
    )


def test_verified_intro_updates_crm_and_obsidian_only_without_payment():
    writer, store = Writer(), Store()
    result = run(writer, store)
    assert result.status == "ready"
    assert [name for name, _ in writer.calls] == ["amocrm", "obsidian"]


def test_confirmed_payment_unlocks_airtable():
    writer, store = Writer(), Store()
    result = run(writer, store, [{"customer_id": "c1", "status": "confirmed",
                                  "kind": "income", "record_id": "r1", "amount": 1}])
    assert "airtable" in result.writes


def test_duplicate_message_has_no_external_writes():
    writer, store = Writer(), Store()
    run(writer, store)
    result = run(writer, store)
    assert result.status == "duplicate"
    assert len(writer.calls) == 2
