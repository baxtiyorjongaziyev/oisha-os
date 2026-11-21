"""Read-only live probe tests; all fixtures are synthetic."""
import os

import pytest

from scripts.prod import probe_daily_priority_seller_routes as diag


class FakeAmo:
    def __init__(self, *, live=False):
        assert live is False
        self.requests = []

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

    monkeypatch.setattr(diag, "AmoCRMTaskCleaner", NoMetadata)
    with pytest.raises(RuntimeError, match="No verified"):
        diag.probe(max_pages=1)
