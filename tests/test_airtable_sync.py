import requests
import pytest

from src.services.core.airtable_sync import AirtableSync


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clear_airtable_caches():
    AirtableSync._records_cache.clear()
    AirtableSync._base_tables_cache.clear()
    AirtableSync._record_url_cache.clear()
    AirtableSync._billing_blocked_until = 0.0
    AirtableSync._billing_block_reason = None
    yield
    AirtableSync._records_cache.clear()
    AirtableSync._base_tables_cache.clear()
    AirtableSync._record_url_cache.clear()
    AirtableSync._billing_blocked_until = 0.0
    AirtableSync._billing_block_reason = None


def test_get_projects_paginates_and_uses_timeouts(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        snapshot = dict(kwargs)
        if "params" in snapshot:
            snapshot["params"] = dict(snapshot["params"])
        calls.append((method, url, snapshot))
        if len(calls) == 1:
            return _FakeResponse(
                payload={
                    "records": [{"id": "rec1", "fields": {"Loyihani nomi?": "A"}}],
                    "offset": "next-page",
                }
            )
        return _FakeResponse(payload={"records": [{"id": "rec2", "fields": {"Loyihani nomi?": "B"}}]})

    monkeypatch.setattr(requests, "request", fake_request)

    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")
    records = sync.get_projects()

    assert [record["id"] for record in records] == ["rec1", "rec2"]
    assert calls[0][2]["timeout"] == AirtableSync.REQUEST_TIMEOUT_SECONDS
    assert calls[0][2]["params"] == {"pageSize": 100}
    assert calls[1][2]["params"]["offset"] == "next-page"


def test_get_projects_retries_transient_network_errors(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.ConnectionError("temporary network issue")
        return _FakeResponse(payload={"records": [{"id": "rec-ok", "fields": {}}]})

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr("src.services.core.airtable_sync.time.sleep", lambda delay: None)

    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")
    records = sync.get_projects()

    assert records == [{"id": "rec-ok", "fields": {}}]
    assert calls["count"] == 2


def test_table_url_encodes_table_names():
    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Logo Brief")

    assert sync.endpoint == "https://api.airtable.com/v0/appBase/Logo%20Brief"


def test_get_projects_uses_ttl_cache_and_deepcopy(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        return _FakeResponse(
            payload={"records": [{"id": "rec1", "fields": {"Name": "Original"}}]}
        )

    monkeypatch.setattr(requests, "request", fake_request)

    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")
    first = sync.get_projects()
    first[0]["fields"]["Name"] = "Mutated"
    second = sync.get_projects()

    assert calls["count"] == 1
    assert second[0]["fields"]["Name"] == "Original"


def test_get_projects_force_refresh_bypasses_cache(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        return _FakeResponse(payload={"records": [{"id": f"rec{calls['count']}"}]})

    monkeypatch.setattr(requests, "request", fake_request)

    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")

    assert sync.get_projects()[0]["id"] == "rec1"
    assert sync.get_projects(force_refresh=True)[0]["id"] == "rec2"
    assert calls["count"] == 2


def test_write_operations_invalidate_records_cache(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        if method == "PATCH":
            return _FakeResponse(payload={"id": "rec1"})
        return _FakeResponse(payload={"records": [{"id": f"rec{calls['count']}"}]})

    monkeypatch.setattr(requests, "request", fake_request)

    sync = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")

    assert sync.get_projects()[0]["id"] == "rec1"
    assert sync.update_project_fields("rec1", {"Loyiha bosqichi": "Next"}) is True
    assert sync.get_projects()[0]["id"] == "rec3"
    assert calls["count"] == 3


def test_billing_limit_starts_shared_cooldown_without_retries(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        return _FakeResponse(
            status_code=429,
            text='{"errors":[{"error":"PUBLIC_API_BILLING_LIMIT_EXCEEDED"}]}',
        )

    monkeypatch.setattr(requests, "request", fake_request)

    first = AirtableSync(api_key="key", base_id="appBase", table_name="Loyihalar")
    second = AirtableSync(api_key="key", base_id="appBase", table_name="Kirim")

    assert first.get_projects(force_refresh=True) == []
    assert second.get_projects(force_refresh=True) == []
    assert calls["count"] == 1
