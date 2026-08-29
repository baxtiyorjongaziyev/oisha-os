"""AMOCRM_REFRESH_TOKEN fallback must fire whenever no usable refresh_token
is loaded — not only when token_data is completely empty.

Real production shape this guards against: `data/amocrm_token.json` exists
(so `_load_token()` "succeeds" and populates `token_data`) but the payload
has lost its `refresh_token` — e.g. a partial write, an access-token-only
snapshot, or an empty `{}` file. The old guard (`if raw_refresh and not
self.token_data`) treated any non-empty `token_data` as fully loaded and
permanently skipped the AMOCRM_REFRESH_TOKEN env fallback, even though a
perfectly good refresh token was sitting in `.env` — the exact
"[AMOCRM] Refresh token topilmadi." lockout seen in production, recoverable
only by a manual re-authorization.
"""

import json

import pytest

from src.services.core.crm.amocrm_sync import AmoCRMSync


@pytest.mark.asyncio
async def test_raw_refresh_fallback_used_when_file_has_access_token_only(
    monkeypatch, tmp_path
):
    """token_data loads successfully but lacks refresh_token -> fallback must fire."""
    token_file = tmp_path / "amocrm_token.json"
    token_file.write_text(json.dumps({"access_token": "stale-access-token"}))
    monkeypatch.setenv("AMOCRM_REFRESH_TOKEN", "env-refresh-token")
    monkeypatch.delenv("AMOCRM_TOKEN_JSON", raising=False)

    amocrm = AmoCRMSync(
        "jonbrandingagency",
        "client-id",
        "client-secret",
        "https://example.test/cb",
        token_file=str(token_file),
    )

    assert amocrm.token_data.get("refresh_token") == "env-refresh-token"
    # The stale access_token loaded from the file must not survive either —
    # it cannot be renewed without a matching refresh_token.
    assert amocrm.access_token is None


@pytest.mark.asyncio
async def test_raw_refresh_fallback_used_when_file_is_empty_dict(monkeypatch, tmp_path):
    token_file = tmp_path / "amocrm_token.json"
    token_file.write_text("{}")
    monkeypatch.setenv("AMOCRM_REFRESH_TOKEN", "env-refresh-token")
    monkeypatch.delenv("AMOCRM_TOKEN_JSON", raising=False)

    amocrm = AmoCRMSync(
        "jonbrandingagency",
        "client-id",
        "client-secret",
        "https://example.test/cb",
        token_file=str(token_file),
    )

    assert amocrm.token_data.get("refresh_token") == "env-refresh-token"


@pytest.mark.asyncio
async def test_raw_refresh_fallback_skipped_when_file_already_has_refresh_token(
    monkeypatch, tmp_path
):
    """A healthy on-disk token must win over the (possibly stale/rotated) env fallback."""
    token_file = tmp_path / "amocrm_token.json"
    token_file.write_text(
        json.dumps({"access_token": "fresh-at", "refresh_token": "fresh-rt"})
    )
    monkeypatch.setenv("AMOCRM_REFRESH_TOKEN", "env-refresh-token")
    monkeypatch.delenv("AMOCRM_TOKEN_JSON", raising=False)

    amocrm = AmoCRMSync(
        "jonbrandingagency",
        "client-id",
        "client-secret",
        "https://example.test/cb",
        token_file=str(token_file),
    )

    assert amocrm.token_data.get("refresh_token") == "fresh-rt"
    assert amocrm.access_token == "fresh-at"


@pytest.mark.asyncio
async def test_no_fallback_available_still_reports_missing(monkeypatch, tmp_path):
    token_file = tmp_path / "amocrm_token.json"
    token_file.write_text(json.dumps({"access_token": "stale-access-token"}))
    monkeypatch.delenv("AMOCRM_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("AMOCRM_TOKEN_JSON", raising=False)

    amocrm = AmoCRMSync(
        "jonbrandingagency",
        "client-id",
        "client-secret",
        "https://example.test/cb",
        token_file=str(token_file),
    )

    assert amocrm.refresh_token() is False
    assert amocrm.last_error == "refresh_token_missing"
