import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers import non_crm_payment_intake as nci

CHAT_ID = -1003854308552
CARD_MSG_ID = 100
ASK_MSG_ID = 101
REPLY_MSG_ID = 102


class FakeDb:
    def __init__(self):
        self.state = {}

    async def get_state(self, key):
        return self.state.get(key)

    async def set_state(self, key, value):
        self.state[key] = value


def _reply_event(text: str, reply_to_msg_id: int = ASK_MSG_ID, bot: bool = False):
    sender = SimpleNamespace(id=8090679294, username="hasan_yahyo", bot=bot)
    return SimpleNamespace(
        chat_id=CHAT_ID,
        id=REPLY_MSG_ID,
        message=SimpleNamespace(message=text, reply_to_msg_id=reply_to_msg_id),
        get_sender=AsyncMock(return_value=sender),
    )


def test_parsers_extract_amount_phone_and_name():
    assert nci.parse_amount_uzs("11 760 000 so'm") == 11760000
    assert nci.parse_amount_uzs("$500") == 0
    assert nci.extract_phone("Telefon: 90 123 45 67") == "+998901234567"
    assert nci.extract_phone("+998 97 335-59-00") == "+998973355900"
    assert nci.extract_client_name("1. Mijoz ismi: Alisher Karimov +998901234567", "ZARVEX") == "Alisher Karimov"


def test_reply_with_phone_creates_won_lead_and_confirms():
    db = FakeDb()
    asyncio.run(
        nci.save_pending_intake(
            db,
            CHAT_ID,
            CARD_MSG_ID,
            ASK_MSG_ID,
            "@hasan_yahyo",
            {"project": '"ZARVEX", "PROFEX" Shartnoma: 11', "amount": "11 760 000 so'm"},
        )
    )
    amocrm = SimpleNamespace(
        create_lead=AsyncMock(return_value=98765),
        add_lead_note=MagicMock(),
        create_standalone_lead=AsyncMock(),
    )
    send = AsyncMock()
    ctx = SimpleNamespace(msg_controller=SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=amocrm)))
    reply_text = (
        "1. Mijoz ismi: Sardor Rahimov +998901234567\n"
        "2. 2ta ekspert tekshiruvi, 2ta Patent xizmati\n"
        "3. Mijozlar tavsiyasi orqali\n"
        "4. Davlat boji yo'q"
    )
    with patch.object(nci, "app_ctx", ctx):
        handled = asyncio.run(nci.handle_non_crm_client_info_reply(_reply_event(reply_text), send))

    assert handled is True
    amocrm.create_lead.assert_awaited_once()
    kwargs = amocrm.create_lead.await_args.kwargs
    assert kwargs["phone"] == "+998901234567"
    assert kwargs["price"] == 11760000
    assert kwargs["status_id"] == 142
    amocrm.add_lead_note.assert_called_once()
    send.assert_awaited_once()
    assert "#98765" in send.await_args.args[2]
    assert json.loads(db.state[nci.pending_intake_key(CHAT_ID, ASK_MSG_ID)])["status"] == "created"


def test_reply_without_phone_creates_standalone_won_lead():
    db = FakeDb()
    asyncio.run(
        nci.save_pending_intake(
            db,
            CHAT_ID,
            CARD_MSG_ID,
            ASK_MSG_ID,
            "@hasan_yahyo",
            {"project": "ZARVEX", "amount": "11 760 000 so'm"},
        )
    )
    amocrm = SimpleNamespace(
        create_lead=AsyncMock(),
        add_lead_note=MagicMock(),
        create_standalone_lead=AsyncMock(return_value=54321),
    )
    send = AsyncMock()
    ctx = SimpleNamespace(msg_controller=SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=amocrm)))
    with patch.object(nci, "app_ctx", ctx):
        handled = asyncio.run(
            nci.handle_non_crm_client_info_reply(_reply_event("2ta patent, tavsiya orqali, davlat boji yo'q"), send)
        )

    assert handled is True
    amocrm.create_standalone_lead.assert_awaited_once()
    assert amocrm.create_standalone_lead.await_args.kwargs["status_id"] == 142
    assert "#54321" in send.await_args.args[2]


def test_second_reply_is_ignored_after_creation():
    db = FakeDb()
    db.state[nci.pending_intake_key(CHAT_ID, ASK_MSG_ID)] = json.dumps({"status": "created", "lead_id": 1})
    amocrm = SimpleNamespace(create_lead=AsyncMock(), create_standalone_lead=AsyncMock())
    send = AsyncMock()
    ctx = SimpleNamespace(msg_controller=SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=amocrm)))
    with patch.object(nci, "app_ctx", ctx):
        handled = asyncio.run(nci.handle_non_crm_client_info_reply(_reply_event("qo'shimcha"), send))

    assert handled is False
    send.assert_not_awaited()
