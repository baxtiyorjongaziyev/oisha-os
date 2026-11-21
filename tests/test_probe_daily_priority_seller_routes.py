"""Read-only live probe tests; all fixtures are synthetic."""
import os
from types import SimpleNamespace

import pytest

from scripts.prod import probe_daily_priority_seller_routes as diag


class FakeAmo:
    def __init__(self, *, live=False):
        assert live is False
        self.requests = []
        self.amo = SimpleNamespace(base_url="https://example.invalid", access_token="synthetic-token")

    def _get(self, path, params=None):
        self.requests.append((path, params))
        if path == "/api/v4/leads/custom_fields":
            return {
                "_embedded": {"custom_fields": [
                    {"id": 1559389, "name": "Sotuvchi"},
                    {"id": 9000000, "name": "Lead manbasi"},
                ]}
            }
        if path == "/api/v4/leads":
            return {
                "_embedded": {"leads": [
                    {
                        "id": 1, "name": "Test lead A",
                        "pipeline_id": 11162698, "status_id": 88871066,
                        "custom_fields_values": [
                            {"field_id": 1559389, "values": [{"value": "Shahnoza"}]}
                        ],
                    },
                    {
                        "id": 2, "name": "Test lead B",
                        "pipeline_id": 11162698, "status_id": 88871066,
                        "_embedded": {"tags": [
                            {"name": "sotuvchi:Rayxona Rahimova"}
                        ]},
                    },
                    {
                        "id": 3, "name": "Test lead C",
                        "pipeline_id": 11162698, "status_id": 88871066,
                        "_embedded": {"tags": [
                            {"name": "sotuvchi:Shahnoza Abdijabborova"},
                            {"name": "sotuvchi:Rayxona Rahimova"},
                        ]},
                    },
                ]}
            }
        raise AssertionError("Unexpected network path")


def test_probe_uses_only_get_and_restores_environment(monkeypatch):
    fake = FakeAmo()
    monkeypatch.setattr(diag, "AmoCRMTaskCleaner", lambda **_: fake)
    monkeypatch.setattr(diag, "SALES_STAGES", [
        (11162698, 88871066, "Kelishuv / Yopish"),
    ])
    monkeypatch.setattr(diag, "get_team", lambda: [
        {"key": "shahnoza", "name": "Shahnoza", "role": "sales"},
        {"key": "rayxona", "name": "Rayxona", "role": "sales"},
    ])
    monkeypatch.setenv("DAILY_PRIORITY_SELLER_FIELD_IDS", "previous")
    result = diag.probe(max_pages=2)

    assert result["mode"] == "READ_ONLY"
    assert result["crm_mutations"] == 0
    assert result["telegram_messages"] == 0
    assert result["verified_seller_fields"] == [
        {"id": 1559389, "name": "Sotuvchi"},
    ]
    assert result["verified_seller_leads"] == {"shahnoza": 1, "rayxona": 1}
    assert result["unassigned_or_conflicting"] == 1
    assert os.environ["DAILY_PRIORITY_SELLER_FIELD_IDS"] == "previous"
    assert [path for path, _ in fake.requests] == [
        "/api/v4/leads/custom_fields", "/api/v4/leads",
    ]


def test_probe_fails_without_metadata(monkeypatch):
    class NoMetadata:
        def __init__(self, **_):
            pass

        def _get(self, path, params):
            assert path == "/api/v4/leads/custom_fields"
            return {"_embedded": {"custom_fields": []}}

        amo = SimpleNamespace(base_url="https://example.invalid", access_token="synthetic")

    monkeypatch.setattr(diag, "AmoCRMTaskCleaner", NoMetadata)
    with pytest.raises(RuntimeError, match="No verified"):
        diag.probe(max_pages=1)


def test_oauth_401_uses_shared_client_refresh_once(monkeypatch):
    """A 401 can be recovered by the production credential rotation guard."""
    from scripts.amocrm_task_cleanup import AmoCRMTaskCleaner

    auth = SimpleNamespace(base_url="https://example.invalid", current="old", refresh_count=0)

    def get_headers():
        return {"Authorization": f"Bearer {auth.current}"}

    def refresh_token():
        auth.refresh_count += 1
        auth.current = "renewed"
        return True

    auth._get_headers = get_headers
    auth.refresh_token = refresh_token
    client = object.__new__(AmoCRMTaskCleaner)
    client.amo = auth
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append((url, headers["Authorization"], params, timeout))
        status = 401 if len(calls) == 1 else 200

        def raise_for_status():
            if status != 200:
                raise RuntimeError(f"HTTP {status}")

        return SimpleNamespace(
            status_code=status,
            json=lambda: {"verified": True},
            raise_for_status=raise_for_status,
        )

    monkeypatch.setattr("scripts.amocrm_task_cleanup.requests.get", fake_get)
    result = diag._read_get(client, "/api/v4/leads/custom_fields", {"page": 1})
    assert result == {"verified": True}
    assert auth.refresh_count == 1
    assert [call[1] for call in calls] == ["Bearer old", "Bearer renewed"]
    assert all(call[2] == {"page": 1} for call in calls)


def test_401_without_refresh_remains_error(monkeypatch):
    """Never conceal invalid integration credentials or loop indefinitely."""
    from scripts.amocrm_task_cleanup import AmoCRMTaskCleaner
    import requests

    auth = SimpleNamespace(
        base_url="https://example.invalid",
        _get_headers=lambda: {"Authorization": "Bearer invalid"},
        refresh_token=lambda: False,
    )
    client = object.__new__(AmoCRMTaskCleaner)
    client.amo = auth
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(1)

        def failed():
            raise requests.HTTPError("HTTP 401 Unauthorized")

        return SimpleNamespace(status_code=401, raise_for_status=failed)

    monkeypatch.setattr("scripts.amocrm_task_cleanup.requests.get", fake_get)
    with pytest.raises(requests.HTTPError, match="401"):
        diag._read_get(client, "/api/v4/leads/custom_fields", {"page": 1})
    assert len(calls) == 1
