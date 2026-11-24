import asyncio
from types import SimpleNamespace

from src.services.core.crm.phone_plus_fixer import build_contact_patch, fix_contact_phones, fix_phone_value


def test_fix_phone_value():
    assert fix_phone_value("998973355900") == "+998973355900"
    assert fix_phone_value("998 97 335-59-00") == "+998973355900"
    assert fix_phone_value("+998973355900") is None
    assert fix_phone_value("79161234567") is None
    assert fix_phone_value("") is None


def _contact(cid, *phones):
    return {"id": cid, "custom_fields_values": [
        {"field_id": 7, "field_code": "PHONE", "values": [{"value": p, "enum_code": "WORK"} for p in phones]}
    ]}


def test_build_patch_keeps_other_values():
    patch = build_contact_patch(_contact(5, "998973355900", "+998901112233"))
    assert patch == {"id": 5, "custom_fields_values": [{"field_id": 7, "values": [
        {"value": "+998973355900", "enum_code": "WORK"},
        {"value": "+998901112233", "enum_code": "WORK"},
    ]}]}
    assert build_contact_patch(_contact(6, "+998973355900")) is None


def test_fix_contact_phones_patches_only_bad():
    calls = []

    class Crm:
        base_url = "https://x"

        async def _request_with_auth(self, fn, url, **kw):
            calls.append((fn.__name__, kw))
            if fn.__name__ == "get":
                body = {"_embedded": {"contacts": [_contact(1, "998973355900"), _contact(2, "+998901112233")]}}
                return SimpleNamespace(status_code=200, json=lambda: body)
            return SimpleNamespace(status_code=200, text="")

    assert asyncio.run(fix_contact_phones(Crm())) == 1
    assert [c[0] for c in calls] == ["get", "patch"]
    assert calls[1][1]["json"][0]["id"] == 1
