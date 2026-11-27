import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers import sales_won_check as swc

CHAT_ID, MSG_ID = -1003854308552, 77
STATE_KEY = f"sales_won_check:{CHAT_ID}:{MSG_ID}"
SELLER = SimpleNamespace(responsible_user_id=7, telegram_user_id=555, seller_name="Rayxona")


class FakeDb:
    def __init__(self):
        self.state = {}
        self.rop = MagicMock()

    async def set_state(self, key, value):
        self.state[key] = value


def _run(*, won_leads, roster=(SELLER,), sender_id=555, card_seller="Rayxona", quiet=False):
    """Run one check with no delay; returns (send mock, db)."""
    db = FakeDb()
    send = AsyncMock()
    fetcher = SimpleNamespace(fetch_won_leads_since=AsyncMock(return_value=list(won_leads)))
    ctx = SimpleNamespace(msg_controller=SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=object())))
    with (
        patch.object(swc, "app_ctx", ctx),
        patch.object(swc, "RopFetcher", return_value=fetcher),
        patch.object(swc, "load_roster", AsyncMock(return_value=list(roster))),
        patch.object(swc, "is_quiet_hours", return_value=quiet),
    ):
        asyncio.run(
            swc.check_won_after_payment(
                send, CHAT_ID, MSG_ID, "@rayxona",
                sender_id=sender_id, card_seller=card_seller, db=db, delay=0,
            )
        )
    return send, db


def test_reminds_seller_when_no_won_lead():
    send, db = _run(won_leads=[{"id": 1, "responsible_user_id": 99}])

    send.assert_awaited_once()
    chat_id, reply_to, text = send.await_args.args
    assert (chat_id, reply_to) == (CHAT_ID, MSG_ID)
    assert "@rayxona" in text and "amoCRM" in text
    assert db.state[STATE_KEY] == "reminded"


def test_silent_when_seller_has_won_lead():
    send, db = _run(won_leads=[{"id": 42, "responsible_user_id": 7}])

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "won:42"


def test_matches_seller_by_card_name_when_telegram_id_unknown():
    send, db = _run(won_leads=[{"id": 42, "responsible_user_id": 7}], sender_id=1, card_seller="rayxona ")

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "won:42"


def test_unknown_seller_is_skipped_without_reminder():
    send, db = _run(won_leads=[], roster=(), card_seller=None)

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "unknown_seller"


def test_quiet_hours_suppress_reminder():
    send, db = _run(won_leads=[], quiet=True)

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "quiet_hours"


def test_crm_failure_does_not_raise_or_remind():
    db = FakeDb()
    send = AsyncMock()
    with (
        patch.object(swc, "app_ctx", SimpleNamespace(msg_controller=None)),
        patch.object(swc, "load_roster", AsyncMock(side_effect=RuntimeError("db down"))),
    ):
        asyncio.run(
            swc.check_won_after_payment(send, CHAT_ID, MSG_ID, "@x", sender_id=555, card_seller=None, db=db, delay=0)
        )

    send.assert_not_awaited()


def test_crm_read_failure_sends_no_reminder():
    from src.services.core.rop.fetchers import RopFetchError

    db = FakeDb()
    send = AsyncMock()
    fetcher = SimpleNamespace(fetch_won_leads_since=AsyncMock(side_effect=RopFetchError("HTTP 500")))
    ctx = SimpleNamespace(msg_controller=SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=object())))
    with (
        patch.object(swc, "app_ctx", ctx),
        patch.object(swc, "RopFetcher", return_value=fetcher),
        patch.object(swc, "load_roster", AsyncMock(return_value=[SELLER])),
        patch.object(swc, "is_quiet_hours", return_value=False),
    ):
        asyncio.run(
            swc.check_won_after_payment(
                send, CHAT_ID, MSG_ID, "@rayxona",
                sender_id=555, card_seller=None, db=db, delay=0,
            )
        )

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "crm_unavailable"
    fetcher.fetch_won_leads_since.assert_awaited_once()
    assert fetcher.fetch_won_leads_since.await_args.kwargs == {"strict": True}


def test_strict_fetch_raises_on_http_error_instead_of_empty_list():
    import asyncio as _aio
    from src.services.core.rop.fetchers import RopFetcher, RopFetchError

    class Resp:
        status_code = 500

    session = MagicMock()
    session.get = MagicMock(return_value=Resp())
    amo = SimpleNamespace(base_url="https://x", _get_headers=lambda: {})
    fetcher = RopFetcher(amo, session=session)

    assert _aio.run(fetcher.fetch_won_leads_since(0)) == []
    try:
        _aio.run(fetcher.fetch_won_leads_since(0, strict=True))
    except RopFetchError:
        pass
    else:
        raise AssertionError("strict fetch must raise on HTTP 500")


def test_strict_fetch_raises_when_pages_incomplete():
    import asyncio as _aio
    from src.services.core.rop.fetchers import RopFetcher, RopFetchError

    class Resp:
        status_code = 200

        def json(self):
            return {"_embedded": {"leads": [{"id": 1}]},
                    "_links": {"next": {"href": "https://x/next"}}}

    session = MagicMock()
    session.get = MagicMock(return_value=Resp())
    amo = SimpleNamespace(base_url="https://x", _get_headers=lambda: {})
    fetcher = RopFetcher(amo, session=session)

    try:
        _aio.run(fetcher.fetch_won_leads_since(0, strict=True))
    except RopFetchError:
        pass
    else:
        raise AssertionError("strict fetch must raise when pages are incomplete")


def test_non_crm_seller_hasanboy_asked_for_client_info_by_tg_id():
    db = FakeDb()
    send = AsyncMock()
    with patch.object(swc, "is_quiet_hours", return_value=False):
        asyncio.run(
            swc.check_won_after_payment(
                send, CHAT_ID, MSG_ID, "@hasan_yahyo",
                sender_id=8090679294, card_seller="Hasan Gaziyev", db=db, delay=0,
            )
        )

    send.assert_awaited_once()
    chat_id, reply_to, text = send.await_args.args
    assert (chat_id, reply_to) == (CHAT_ID, MSG_ID)
    assert "@hasan_yahyo" in text
    assert "Mijoz ismi" in text and "Davlat boji" in text
    assert "amoCRM" not in text
    assert db.state[STATE_KEY] == "asked_client_info"


def test_non_crm_seller_hasanboy_matched_by_username_or_card_name():
    db = FakeDb()
    send = AsyncMock()
    with patch.object(swc, "is_quiet_hours", return_value=False):
        asyncio.run(
            swc.check_won_after_payment(
                send, CHAT_ID, MSG_ID, "@hasan_yahyo",
                sender_id=None, card_seller="Hasan Gaziyev", db=db, delay=0,
            )
        )

    send.assert_awaited_once()
    assert db.state[STATE_KEY] == "asked_client_info"


def test_non_crm_seller_respects_quiet_hours():
    db = FakeDb()
    send = AsyncMock()
    with patch.object(swc, "is_quiet_hours", return_value=True):
        asyncio.run(
            swc.check_won_after_payment(
                send, CHAT_ID, MSG_ID, "@hasan_yahyo",
                sender_id=8090679294, card_seller="Hasan Gaziyev", db=db, delay=0,
            )
        )

    send.assert_not_awaited()
    assert db.state[STATE_KEY] == "quiet_hours"
