def test_gsheets_client_has_scopes():
    """Star import skips underscore names; client must import _GSHEET_SCOPES explicitly."""
    from src.services.core.finance.gsheets import client

    assert client._GSHEET_SCOPES
    assert all(s.startswith("https://www.googleapis.com/auth/") for s in client._GSHEET_SCOPES)
