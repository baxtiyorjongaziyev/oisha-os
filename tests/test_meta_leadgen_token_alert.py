import asyncio
from unittest.mock import MagicMock, patch

from src.schedulers import meta_leadgen_scheduler as sched


def _expired_token_response():
    resp = MagicMock()
    resp.status_code = 400
    resp.json.return_value = {
        "error": {"type": "OAuthException", "code": 190, "error_subcode": 463, "message": "Session has expired"}
    }
    return resp


def test_expired_token_alerts_once_and_skips_fallback_forms(monkeypatch):
    monkeypatch.setenv("META_PAGE_ACCESS_TOKEN", "expired")
    monkeypatch.setattr(sched, "_last_auth_alert_at", 0.0)
    with patch.object(sched.requests, "get", return_value=_expired_token_response()) as get, \
         patch("src.services.core.instagram.leadgen_watchdog.send_admin_alert", return_value=True) as alert:
        assert asyncio.run(sched.poll_leadgen_forms_once()) == 0
        assert asyncio.run(sched.poll_leadgen_forms_once()) == 0

    assert alert.call_count == 1
    assert "190" in alert.call_args[0][0]
    assert alert.call_args.kwargs.get("technical") is True
    assert get.call_count == 2


def test_non_auth_error_stays_generic():
    resp = MagicMock()
    resp.status_code = 500
    resp.json.return_value = {"error": {"type": "GraphMethodException", "code": 1}}
    try:
        sched._raise_for_meta_error(resp)
    except sched.MetaAuthError:
        raise AssertionError("500 must not be treated as a token problem")
    except RuntimeError:
        pass


def test_permission_error_on_form_list_keeps_fallback_forms(monkeypatch):
    monkeypatch.setenv("META_PAGE_ACCESS_TOKEN", "valid")
    monkeypatch.setattr(sched, "_last_auth_alert_at", 0.0)
    perm = MagicMock()
    perm.status_code = 403
    perm.json.return_value = {"error": {"type": "OAuthException", "code": 200, "message": "Permissions error"}}
    empty = MagicMock()
    empty.status_code = 200
    empty.json.return_value = {"data": []}

    def fake_get(url, params=None, timeout=None):
        return perm if url.endswith("/leadgen_forms") else empty

    with patch.object(sched.requests, "get", side_effect=fake_get) as get, \
         patch("src.services.core.instagram.leadgen_watchdog.send_admin_alert", return_value=True) as alert:
        assert asyncio.run(sched.poll_leadgen_forms_once()) == 0

    assert alert.call_count == 0
    polled = [c.args[0] for c in get.call_args_list if c.args[0].endswith("/leads")]
    assert len(polled) >= 1
