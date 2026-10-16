from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.api_server.oauth import _safe_redirect_target, _safe_login_next


def test_safe_redirect_target_allows_whitelisted():
    assert _safe_redirect_target("/capi") == "/capi"
    assert _safe_redirect_target("/api/marketing/capi/console") == "/api/marketing/capi/console"
    assert _safe_redirect_target("/") == "/"


def test_safe_redirect_target_blocks_open_redirects():
    assert _safe_redirect_target("https://attacker.com") == "/"
    assert _safe_redirect_target("//attacker.com") == "/"
    assert _safe_redirect_target("javascript:alert(1)") == "/"
    assert _safe_redirect_target("/admin/unauthorized") == "/"
    assert _safe_redirect_target(None) == "/"
    assert _safe_redirect_target("") == "/"


def test_safe_login_next_whitelisted():
    assert _safe_login_next("/capi") == "/capi"
    assert _safe_login_next("/api/marketing/capi/console") == "/api/marketing/capi/console"


def test_safe_login_next_blocks_untrusted():
    assert _safe_login_next("https://attacker.com") == ""
    assert _safe_login_next("<script>alert(1)</script>") == ""
    assert _safe_login_next(None) == ""


@pytest.mark.asyncio
async def test_telegram_extension_send_sanitizes_errors():
    from src.services.api_server.telegram_extension import telegram_extension_send
    
    request = MagicMock()
    request.json = AsyncMock(side_effect=RuntimeError("Sensitive internal database connection failed"))
    
    res = await telegram_extension_send(request)
    assert res["success"] is False
    assert res["error"] == "Telegram send request failed"
    assert "Sensitive" not in res["error"]
