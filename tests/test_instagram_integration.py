"""
Unit tests for Meta Instagram Webhook & Agent integration
"""
import pytest
import hmac
import hashlib
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.api_server import app
from src.services.core.instagram_agent import (
    verify_signature,
    notify_crm,
    like_comment,
    reply_to_comment,
    send_ig_reply,
    fetch_media_caption,
    generate_comment_reply,
    process_instagram_webhook,
)

client = TestClient(app)


def test_verify_signature():
    payload = b"test_payload"
    secret = "test_secret"
    expected_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_signature(payload, expected_sig, secret) is True
    assert verify_signature(payload, "invalid_sig", secret) is False
    assert verify_signature(payload, expected_sig, "") is True
    assert verify_signature("test_payload", expected_sig, secret) is True
    assert verify_signature({"key": "value"}, "invalid_sig", secret) is False


@patch.dict("os.environ", {"INSTAGRAM_VERIFY_TOKEN": "correct_token"})
def test_webhook_verification_success():
    response = client.get(
        "/api/instagram/webhook",
        params={
            "hub_mode": "subscribe",
            "hub_verify_token": "correct_token",
            "hub_challenge": "12345challenge"
        }
    )
    assert response.status_code == 200
    assert response.text == "12345challenge"


@patch.dict("os.environ", {"INSTAGRAM_VERIFY_TOKEN": "correct_token"})
def test_webhook_verification_failure():
    response = client.get(
        "/api/instagram/webhook",
        params={
            "hub_mode": "subscribe",
            "hub_verify_token": "wrong_token",
            "hub_challenge": "12345challenge"
        }
    )
    assert response.status_code == 403
    assert "Verification token mismatch" in response.text


@patch("src.services.core.instagram_agent.requests.post")
def test_like_comment(mock_post):
    mock_post.return_value.status_code = 200
    assert like_comment("comment_123", "valid_token") is True
    mock_post.assert_called_once()
    assert "comment_123/likes" in mock_post.call_args[0][0]

    # No token
    assert like_comment("comment_123", "") is False

    # Failure
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Error"
    assert like_comment("comment_123", "valid_token") is False


@patch("src.services.core.instagram_agent.requests.post")
def test_reply_to_comment(mock_post):
    mock_post.return_value.status_code = 200
    assert reply_to_comment("comment_123", "Hello!", "valid_token") is True
    mock_post.assert_called_once()
    assert "comment_123/replies" in mock_post.call_args[0][0]

    # No token
    assert reply_to_comment("comment_123", "Hello!", "") is False

    # Failure
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Error"
    assert reply_to_comment("comment_123", "Hello!", "valid_token") is False


@patch("src.services.core.instagram_agent.requests.get")
def test_fetch_media_caption(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"caption": "Post haqida ma'lumot"}
    assert fetch_media_caption("media_123", "valid_token") == "Post haqida ma'lumot"

    # No token
    assert fetch_media_caption("media_123", "") == ""

    # Failure
    mock_get.return_value.status_code = 400
    assert fetch_media_caption("media_123", "valid_token") == ""


@pytest.mark.asyncio
async def test_generate_comment_reply():
    with patch("src.services.utils.free_ai_router.get_free_ai_router") as mock_router:
        mock_instance = MagicMock()
        mock_instance.generate_text = AsyncMock(return_value=MagicMock(text="Branding haqida zo'r fikr!"))
        mock_router.return_value = mock_instance

        reply = await generate_comment_reply("Qoyilmaqom dizayn!", "Yangi loyiha", "Ali")
        assert "Branding" in reply


@patch("src.services.core.instagram_agent.requests.post")
def test_send_ig_reply(mock_post):
    mock_post.return_value.status_code = 200
    assert send_ig_reply("user_123", "Hello DM!", "valid_token") is True
    mock_post.assert_called_once()
    assert "me/messages" in mock_post.call_args[0][0]

    # No token
    assert send_ig_reply("user_123", "Hello DM!", "") is False

    # Failure
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Error"
    assert send_ig_reply("user_123", "Hello DM!", "valid_token") is False


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.requests.post")
async def test_notify_crm(mock_post):
    mock_post.return_value.status_code = 200

    with patch("src.services.core.instagram_agent.settings") as mock_settings:
        mock_settings.CRM_GROUP_ID = -100123456
        mock_settings.CRM_TOPIC_ID = 5
        mock_settings.BOT_TOKEN.get_secret_value.return_value = "fake_bot_token"

        notify_crm(
            source="Instagram DM",
            user_name="Botir",
            user_id="ig_12345",
            message="Salom, narxlarni bering",
            reply="[LEAD_REPORT: QUALITY=sifatli] Assalomu alaykum! Narxlarimiz..."
        )

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "fake_bot_token" in args[0]
        assert kwargs["json"]["chat_id"] == -100123456
        assert kwargs["json"]["message_thread_id"] == 5
        assert "Sifatli" in kwargs["json"]["text"]
        assert "Botir" in kwargs["json"]["text"]


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.send_ig_reply")
@patch("src.services.core.instagram_agent.notify_crm")
@patch("src.services.core.instagram_agent.AutonomousSalesAgent")
async def test_process_instagram_webhook_dm(mock_agent_class, mock_notify, mock_send_reply):
    mock_db = AsyncMock()
    mock_db.log_message = AsyncMock()
    mock_db.upsert_user = AsyncMock()

    mock_agent_instance = MagicMock()
    mock_agent_instance.handle_incoming = AsyncMock(return_value={
        "response": "[SAVE_INFO: phone=+998991234567] Salom, xabarni qabul qildim"
    })
    mock_agent_class.return_value = mock_agent_instance

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "entry_1",
                "messaging": [
                    {
                        "sender": {"id": "112233"},
                        "message": {"text": "Qalay ishlar?"}
                    }
                ]
            }
        ]
    }

    await process_instagram_webhook(payload, mock_db)

    mock_db.log_message.assert_any_call("ig_112233", "Qalay ishlar?", is_ai=False)
    mock_db.log_message.assert_any_call("ig_112233", "Salom, xabarni qabul qildim", is_ai=True)
    mock_db.upsert_user.assert_called_once_with("ig_112233", "Foydalanuvchi", phone="+998991234567")
    from unittest.mock import ANY
    mock_send_reply.assert_called_once_with("112233", "Salom, xabarni qabul qildim", ANY)
    mock_notify.assert_called_once_with("Instagram DM", "Foydalanuvchi", "112233", "Qalay ishlar?", "[SAVE_INFO: phone=+998991234567] Salom, xabarni qabul qildim")


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.generate_comment_reply", return_value="Rahmat sharhingiz uchun! Narxlarimiz...")
@patch("src.services.core.instagram_agent.notify_crm")
async def test_process_instagram_webhook_comment_flow(
    mock_notify, mock_gen_reply, mock_reply_comment
):
    mock_db = AsyncMock()
    mock_db.log_message = AsyncMock()

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "page_ig_id",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comm_999",
                            "text": "Narxi qancha?",
                            "verb": "add",
                            "from": {
                                "id": "user_888",
                                "username": "anvar_brand"
                            }
                        }
                    }
                ]
            }
        ]
    }

    from unittest.mock import ANY
    await process_instagram_webhook(payload, mock_db)

    # 1. Incoming log
    mock_db.log_message.assert_any_call("ig_comment_user_888", "COMMENT: Narxi qancha?", is_ai=False)
    # 3. Outgoing log
    mock_db.log_message.assert_any_call("ig_comment_user_888", "Rahmat sharhingiz uchun! Narxlarimiz...", is_ai=True)
    # 4. Reply to comment called
    mock_reply_comment.assert_called_once_with("comm_999", "Rahmat sharhingiz uchun! Narxlarimiz...", ANY)
    # 5. Notify CRM called
    mock_notify.assert_called_once_with("Instagram Comment", "anvar_brand", "user_888", "Narxi qancha?", "Rahmat sharhingiz uchun! Narxlarimiz...")


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.generate_comment_reply")
async def test_process_instagram_webhook_comment_loop_protection(
    mock_gen_reply, mock_reply_comment
):
    mock_db = AsyncMock()

    with patch("src.services.core.instagram_agent.settings") as mock_settings:
        mock_settings.META_INSTAGRAM_USER_ID = "my_business_id"
        mock_settings.META_PAGE_ACCESS_TOKEN.get_secret_value.return_value = "token"

        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "my_business_id",
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "id": "comm_111",
                                "text": "Bizning o'z javobimiz",
                                "verb": "add",
                                "from": {
                                    "id": "my_business_id",
                                    "username": "our_account"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        await process_instagram_webhook(payload, mock_db)

        # Should be skipped due to loop protection
        mock_reply_comment.assert_not_called()
        mock_gen_reply.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.generate_comment_reply")
async def test_process_instagram_webhook_comment_filters(
    mock_gen_reply, mock_reply_comment
):
    mock_db = AsyncMock()

    # 1. Verb is not "add" (e.g. "remove" or "edited")
    payload_verb = {
        "object": "instagram",
        "entry": [
            {
                "id": "page_id",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comm_222",
                            "text": "Deleted comment",
                            "verb": "remove",
                            "from": {"id": "user_333", "username": "some_user"}
                        }
                    }
                ]
            }
        ]
    }
    await process_instagram_webhook(payload_verb, mock_db)
    mock_reply_comment.assert_not_called()

    # 2. Field is not "comments" (e.g. "feed", "mentions")
    payload_field = {
        "object": "instagram",
        "entry": [
            {
                "id": "page_id",
                "changes": [
                    {
                        "field": "live_comments",
                        "value": {
                            "id": "comm_444",
                            "text": "Other event",
                            "verb": "add",
                            "from": {"id": "user_555", "username": "other_user"}
                        }
                    }
                ]
            }
        ]
    }
    await process_instagram_webhook(payload_field, mock_db)
    mock_reply_comment.assert_not_called()


def test_extract_caption_keywords():
    from src.services.core.instagram.lead_qualifier import extract_caption_keywords
    cap1 = "Yangi fast-food loyihamiz! Izohda 'NOM' deb yozing, nomlarni yuboramiz."
    assert "nom" in extract_caption_keywords(cap1)

    cap2 = "Brendingizni rivojlantiring. Kommentlarda 'BREND' deb qoldiring!"
    assert "brend" in extract_caption_keywords(cap2)

    cap3 = "Oddiy post matni, hech qanday kalit so'zsiz."
    assert extract_caption_keywords(cap3) == []


def test_should_trigger_dm():
    from src.services.core.instagram.lead_qualifier import should_trigger_dm
    # Static keyword
    trig1, kw1 = should_trigger_dm("Menga yangi nom kerak", "")
    assert trig1 is True
    assert kw1 == "nom"

    trig2, kw2 = should_trigger_dm("Logo dizayn narxi qancha?", "")
    assert trig1 is True

    # Caption keyword match
    trig3, kw3 = should_trigger_dm("START", "Izohda 'START' deb yozing")
    assert trig3 is True
    assert kw3 == "start"

    # Any real message reaches out (DM-everyone policy)
    trig4, kw4 = should_trigger_dm("Zo'r rasm ekan", "Oddiy post")
    assert trig4 is True

    # Emoji-only / lone praise / punctuation is NOT a lead
    assert should_trigger_dm("🔥🔥🔥", "") == (False, "")
    assert should_trigger_dm("👍", "") == (False, "")
    assert should_trigger_dm("!!!", "") == (False, "")
    assert should_trigger_dm("Zo'r", "") == (False, "")


def test_generate_initial_dm_message():
    from src.services.core.instagram.lead_qualifier import generate_initial_dm_message
    msg = generate_initial_dm_message("Sardor", "nom", "Fast-food post")
    assert "Sardor" in msg
    assert "Baxtiyor Gaziyev" in msg
    assert "menejerlari Oishaman" in msg
    assert "Jon Branding" not in msg
    assert "nomlash" in msg


@patch("requests.post")
def test_send_ig_private_reply(mock_post):
    from src.services.core.instagram_agent import send_ig_private_reply
    mock_post.return_value.status_code = 200
    res = send_ig_private_reply("comm_123", "Salom Direct!", "fake_token")
    assert res is True
    assert mock_post.called
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["json"]["recipient"]["comment_id"] == "comm_123"


@pytest.mark.asyncio
@patch("src.services.core.instagram_agent.reply_to_comment")
@patch("src.services.core.instagram_agent.generate_comment_reply")
@patch("src.services.core.instagram_agent.send_ig_private_reply")
async def test_process_instagram_webhook_with_dm_trigger(
    mock_priv_reply, mock_gen_reply, mock_reply_comm
):
    from src.services.core.instagram_agent import process_instagram_webhook
    mock_db = AsyncMock()
    mock_gen_reply.return_value = "Izohingiz uchun rahmat! Directga yozdim."

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "page_id",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comm_999",
                            "text": "Menga fast-food uchun nom kerak",
                            "verb": "add",
                            "from": {"id": "user_888", "username": "tadbirkor_ali"}
                        }
                    }
                ]
            }
        ]
    }

    await process_instagram_webhook(payload, mock_db)
    mock_reply_comm.assert_called_once()
    mock_priv_reply.assert_called_once()
    assert mock_priv_reply.call_args[0][0] == "comm_999"

