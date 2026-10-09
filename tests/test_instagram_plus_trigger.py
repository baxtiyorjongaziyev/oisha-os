"""Target reklamadagi "+" kommentlari uchun DM avtomatizatsiyasi."""
from unittest.mock import AsyncMock, patch

import pytest

from src.services.core.instagram.agent_constants import (
    PLUS_COMMENT_DM_TEMPLATE,
    match_comment_keyword_automation,
)
from src.services.core.instagram_agent import process_instagram_webhook


@pytest.mark.parametrize("text", ["+", "++", " + ", "+ +", "+++\n"])
def test_plus_only_comment_matches(text):
    assert match_comment_keyword_automation(text) == PLUS_COMMENT_DM_TEMPLATE


@pytest.mark.parametrize("text", ["+998 90 123 45 67", "zo'r +", "", "1+1", "rahmat"])
def test_plus_with_other_text_does_not_match(text):
    assert match_comment_keyword_automation(text) != PLUS_COMMENT_DM_TEMPLATE


def _comment_payload(text, media):
    value = {"id": "comm_1", "text": text, "verb": "add", "from": {"id": "user_1", "username": "ali"}}
    if media is not None:
        value["media"] = media
    return {"object": "instagram", "entry": [{"id": "page_ig_id", "changes": [{"field": "comments", "value": value}]}]}


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.send_ig_private_reply", return_value=True)
@patch("src.services.core.instagram_agent.notify_crm")
async def test_plus_comment_on_dark_post_ad_sends_dm(mock_notify, mock_private, mock_ack):
    db = AsyncMock()
    payload = _comment_payload("+", {"id": "media_1", "ad_id": "120211", "media_product_type": "AD"})

    await process_instagram_webhook(payload, db)

    mock_private.assert_called_once()
    assert mock_private.call_args[0][:2] == ("comm_1", PLUS_COMMENT_DM_TEMPLATE)
    mock_ack.assert_called_once()
    assert mock_notify.call_args[0][0] == "Instagram Reklama (ad_id: 120211) (keyword automation)"


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.send_ig_private_reply", return_value=True)
@patch("src.services.core.instagram_agent.notify_crm")
async def test_plus_comment_on_organic_post_keeps_comment_source(mock_notify, mock_private, mock_ack):
    await process_instagram_webhook(_comment_payload("+", None), AsyncMock())

    mock_private.assert_called_once()
    assert mock_notify.call_args[0][0] == "Instagram Comment (keyword automation)"
