"""
Tests for Instagram 'Brend' Video Lead Flow, Qualification & Customer 360 Pipeline.
"""
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from src.services.core.instagram.agent_constants import (
    BREND_COMMENT_DM_TEMPLATE,
    BREND_COMMENT_PUBLIC_REPLIES,
    match_comment_keyword_automation,
    get_public_ack_for_comment,
    TARGET_BREND_VIDEO_SHORTCODE,
)
from src.services.core.instagram.brend_lead_flow import (
    is_brend_keyword,
    handle_brend_comment_trigger,
    process_brend_dm_conversation,
    get_brend_followup_message,
    format_customer_360_alert,
)
from src.services.core.instagram_agent import process_instagram_webhook


@pytest.mark.parametrize("text", ["Brend", "brend", "BRAND", "бренд", "Brend kerak", "Menga brending kerak"])
def test_is_brend_keyword_positive(text):
    assert is_brend_keyword(text) is True


@pytest.mark.parametrize("text", ["salom", "narxi qancha", "zo'r", "+", "rahmat"])
def test_is_brend_keyword_negative(text):
    assert is_brend_keyword(text) is False


def test_brend_comment_keyword_automation_matches():
    template = match_comment_keyword_automation("Brend")
    assert template == BREND_COMMENT_DM_TEMPLATE


def test_brend_public_ack_is_natural():
    ack = get_public_ack_for_comment("Brend")
    assert ack in BREND_COMMENT_PUBLIC_REPLIES
    assert "Sizga DM'dan yozib qo'ydik!" not in ack  # Not robotic


@pytest.mark.asyncio
@patch("src.services.core.instagram.brend_lead_flow.like_comment")
@patch("src.services.core.instagram.brend_lead_flow.reply_to_comment")
@patch("src.services.core.instagram.brend_lead_flow.send_ig_private_reply", return_value=True)
async def test_handle_brend_comment_trigger(mock_private, mock_reply, mock_like):
    db = AsyncMock()
    mock_store = MagicMock()
    mock_store.is_comment_processed.return_value = False
    mock_store.has_user_received_dm.return_value = False
    mock_store.claim_comment.return_value = True

    success = await handle_brend_comment_trigger(
        comment_id="comm_123",
        comment_text="Brend",
        commenter_name="sardor_biz",
        commenter_id="user_456",
        access_token="fake_token",
        db=db,
        store=mock_store,
    )
    assert success is True
    mock_like.assert_called_once_with("comm_123", "fake_token")
    mock_reply.assert_called_once()
    mock_private.assert_called_once_with("comm_123", BREND_COMMENT_DM_TEMPLATE, "fake_token")
    mock_store.record_dm_success.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.core.instagram.lead_qualifier.generate_qualifying_dm_response")
@patch("src.services.core.instagram.lead_qualifier.sync_lead_to_amocrm", return_value=12345)
@patch("src.services.core.instagram.brend_lead_flow.send_ig_reply", return_value=True)
@patch("src.services.customer_360.collector.Customer360Collector.collect_profile")
async def test_process_brend_dm_conversation_with_phone(mock_collect, mock_send, mock_sync, mock_ai):
    mock_ai.return_value = (
        "Qabul qildim, katta rahmat! Tez orada o'zim bog'lanaman 🤝 "
        "[SAVE_INFO: brand=Elegance Wear] [SAVE_INFO: industry=Kiyim-kechak] [SAVE_INFO: phone=+998901234567]"
    )
    from src.services.customer_360.models import Customer360Profile
    dummy_profile = Customer360Profile(name="Sardor", phone="+998901234567", amocrm_lead_id=12345)
    mock_collect.return_value = dummy_profile

    db = AsyncMock()
    res = await process_brend_dm_conversation(
        sender_id="user_456",
        user_message="Mening brendim Elegance Wear, kiyim do'koni. Tel: +998901234567",
        history=[],
        commenter_name="Sardor",
        access_token="fake_token",
        db=db,
        is_brend_lead=True,
    )

    assert "Qabul qildim" in res["reply"]
    assert "[SAVE_INFO" not in res["reply"]  # Cleaned
    assert res["info"]["brand"] == "Elegance Wear"
    assert res["info"]["phone"] == "+998901234567"
    mock_sync.assert_called_once()
    mock_collect.assert_called_once()
    assert res["profile_360"] is not None


def test_format_customer_360_alert():
    from src.services.customer_360.models import Customer360Profile
    profile = Customer360Profile(
        name="Jasur",
        phone="+998901234567",
        instagram_handle="jasur_official",
        amocrm_lead_id=999,
        amocrm_status="Kelishuv",
        amocrm_budget=5000000,
        responsible_manager="Aziz",
    )
    alert = format_customer_360_alert(profile, brand_name="Apex Logistics", industry="Logistika")
    assert "Jasur" in alert
    assert "+998901234567" in alert
    assert "Apex Logistics" in alert
    assert "Logistika" in alert
    assert TARGET_BREND_VIDEO_SHORTCODE in alert


def test_get_brend_followup_message():
    msg_stage1 = get_brend_followup_message(stage=1)
    assert len(msg_stage1) > 20
    assert msg_stage1.startswith("Assalomu alaykum!")
    assert "Salom" not in msg_stage1
    assert "fikrlashib" not in msg_stage1

    msg_stage2 = get_brend_followup_message(stage=2, brand_name="Chust Pichoq", industry="Pichoqchilik")
    assert msg_stage2.startswith("Assalomu alaykum!")
    assert "Chust Pichoq" in msg_stage2
    assert "Telegram" in msg_stage2
    assert "fikrlashib" not in msg_stage2


def test_no_salom_or_fikrlashib_in_constants():
    assert "Salom" not in BREND_COMMENT_DM_TEMPLATE
    assert "fikrlashib" not in BREND_COMMENT_DM_TEMPLATE
    for reply in BREND_COMMENT_PUBLIC_REPLIES:
        assert not reply.startswith("Salom")
        assert "fikrlashib" not in reply


@pytest.mark.asyncio
@patch("src.services.core.instagram.brend_lead_flow.like_comment")
@patch("src.services.core.instagram.brend_lead_flow.reply_to_comment")
@patch("src.services.core.instagram.brend_lead_flow.send_ig_private_reply", return_value=True)
async def test_handle_need_comment_trigger_positive(mock_private, mock_reply, mock_like):
    from src.services.core.instagram.brend_lead_flow import handle_need_comment_trigger
    db = AsyncMock()
    mock_store = MagicMock()
    mock_store.is_comment_processed.return_value = False
    mock_store.has_user_received_dm.return_value = False
    mock_store.claim_comment.return_value = True

    # User asks a question about patenting
    success = await handle_need_comment_trigger(
        comment_id="comm_777",
        comment_text="Patentlash qanday bo'ladi?",
        commenter_name="shoxrux_biz",
        commenter_id="user_888",
        access_token="fake_token",
        post_caption="Biznesingizni himoya qiling",
        db=db,
        store=mock_store,
    )
    assert success is True
    mock_like.assert_called_once_with("comm_777", "fake_token")
    mock_private.assert_called_once()
    assert "comm_777" == mock_private.call_args[0][0]
    mock_reply.assert_called_once()
    mock_store.record_dm_success.assert_called_once()


@pytest.mark.asyncio
async def test_handle_need_comment_trigger_pure_praise_skipped():
    from src.services.core.instagram.brend_lead_flow import handle_need_comment_trigger
    # Pure praise should not trigger DM
    success = await handle_need_comment_trigger(
        comment_id="comm_888",
        comment_text="Zo'r gap yo'q!",
        commenter_name="nodir",
        commenter_id="user_999",
        access_token="fake_token",
    )
    assert success is False


