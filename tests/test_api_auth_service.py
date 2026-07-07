import hashlib
import hmac
import time

from src.api import auth_service


def _valid_hash(fields, bot_token):
    dcs = auth_service.build_telegram_data_check_string(fields)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    return hmac.new(secret_key, dcs.encode(), hashlib.sha256).hexdigest()


def test_verify_telegram_hash_accepts_valid_and_rejects_tampered():
    bot_token = "123:abc"
    fields = {"id": "42", "first_name": "Aziz", "auth_date": "1700000000", "username": "aziz"}
    good = _valid_hash(fields, bot_token)

    assert auth_service.verify_telegram_hash(fields, bot_token, good) is True
    assert auth_service.verify_telegram_hash(fields, bot_token, good[:-1] + "0") is False
    assert auth_service.verify_telegram_hash(fields, bot_token, "") is False


def test_data_check_string_ignores_none_and_sorts():
    fields = {"id": "1", "first_name": "A", "username": None}
    assert auth_service.build_telegram_data_check_string(fields) == "first_name=A\nid=1"


def test_auth_date_freshness_window():
    assert auth_service.is_auth_date_fresh(int(time.time())) is True
    assert auth_service.is_auth_date_fresh(int(time.time()) - 100000) is False
    assert auth_service.is_auth_date_fresh(None) is True


def test_session_jwt_roundtrip_and_rejects_wrong_secret():
    token = auth_service.issue_session_jwt(
        user_id=7, username="aziz", first_name="Aziz", role="client", secret="s3cret"
    )
    payload = auth_service.decode_session_jwt(token, "s3cret")
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["role"] == "client"
    assert auth_service.decode_session_jwt(token, "wrong") is None
    assert auth_service.decode_session_jwt("garbage", "s3cret") is None
