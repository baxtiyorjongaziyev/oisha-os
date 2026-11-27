"""Field/price transfer during Telegram <-> phone deal auto-merge."""
import asyncio
from types import SimpleNamespace

from src.services.core.crm.tg_amo_bridge import executor
from src.services.core.crm.tg_amo_bridge.executor import build_field_transfer


def test_fill_only_transfer_never_overwrites():
    source = {
        "price": 5000000,
        "custom_fields_values": [
            {"field_id": 1, "values": [{"value": "Instagram"}]},
            {"field_id": 2, "values": [{"value": "source-only"}]},
            {"field_id": 3, "values": [{"enum_id": 77, "value": "Toshkent"}]},
            {"field_id": 4, "values": [{"value": ""}]},
        ],
    }
    target = {
        "price": 0,
        "custom_fields_values": [{"field_id": 1, "values": [{"value": "Telegram"}]}],
    }
    payload = build_field_transfer(source, target)
    assert payload["price"] == 5000000
    ids = {f["field_id"] for f in payload["custom_fields_values"]}
    assert ids == {2, 3}
    enum_field = next(f for f in payload["custom_fields_values"] if f["field_id"] == 3)
    assert enum_field["values"] == [{"value": "Toshkent", "enum_id": 77}]


def test_target_price_kept():
    assert build_field_transfer({"price": 10}, {"price": 99}) == {}


class _CRM:
    def __init__(self, leads, patch_ok=True):
        self.leads = leads
        self.patch_ok = patch_ok
        self.patches = []

    async def get_lead(self, lead_id):
        return self.leads.get(lead_id)

    async def patch_lead(self, lead_id, payload):
        self.patches.append((lead_id, payload))
        return self.patch_ok


def test_transfer_patches_target():
    crm = _CRM({1: {"price": 7}, 2: {"price": 0}})
    ok, copied = asyncio.run(executor._transfer_lead_fields(crm, 1, 2))
    assert ok and copied == 1
    assert crm.patches == [(2, {"price": 7})]


def test_transfer_failure_blocks_close():
    crm = _CRM({1: {"price": 7}, 2: {"price": 0}}, patch_ok=False)
    ok, _ = asyncio.run(executor._transfer_lead_fields(crm, 1, 2))
    assert ok is False


def test_missing_lead_is_failure():
    crm = _CRM({2: {"price": 0}})
    ok, _ = asyncio.run(executor._transfer_lead_fields(crm, 1, 2))
    assert ok is False


def test_crm_without_patch_is_noop():
    ok, copied = asyncio.run(executor._transfer_lead_fields(SimpleNamespace(), 1, 2))
    assert ok and copied == 0
