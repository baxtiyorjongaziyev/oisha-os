import asyncio
from unittest.mock import AsyncMock, patch

from src.services.core.dispatcher.handlers_welcome import (
    build_owner_notice_from_dict,
    build_welcome_text,
)
from src.services.core.telegram.ai_features.workflows import handle_botnews_service_update


def _update(wa, uid=5, first="Ali"):
    return {"update_id": 1, "message": {"chat": {"id": uid}, "from": {"id": uid, "first_name": first},
                                         "write_access_allowed": wa}}


def test_welcome_text_escapes_html():
    assert "Ali &lt;3" in build_welcome_text("Ali <3")
    assert "alaykum!" in build_welcome_text(None)
    assert "/ulanish" not in build_welcome_text("Ali", invited=False)


def test_owner_notice():
    text = build_owner_notice_from_dict({"id": 7, "first_name": "Vali"})
    assert "Vali" in text and "id 7" in text and "@" not in text


def _run(update, owner="1"):
    call = AsyncMock()
    with patch("src.services.core.telegram.ai_features.bot_api_client.TelegramBotAPI10Client") as cls, \
         patch.dict("os.environ", {"OWNER_ID": owner}):
        cls.return_value.call = call
        res = asyncio.run(handle_botnews_service_update(update, token="t"))
    return res, call


def test_invite_greets_and_notifies_owner():
    res, call = _run(_update({"inviter": {"id": 1}}))
    assert res["greeted"] and call.await_count == 2
    assert "/ulanish" in call.await_args_list[0].args[1]["text"]
    assert call.await_args_list[1].args[1]["chat_id"] == 1


def test_non_invite_grant_generic_no_owner_notice():
    res, call = _run(_update({"from_request": True}))
    assert call.await_count == 1
    assert "/ulanish" not in call.await_args.args[1]["text"]


def test_owner_self_not_notified():
    _, call = _run(_update({"inviter": {"id": 1}}, uid=1))
    assert call.await_count == 1
