"""AmoCRM kontakt adapteri (mavjud AmoCRM klienti orqali)."""

import asyncio
import logging

import requests

from ..models import Person, display_name
from .base import NAME_PHONE, keys_of, norm_phone, result, split_name

logger = logging.getLogger(__name__)
TAG = "community"


def _phone_of(contact: dict) -> str:
    for f in contact.get("custom_fields_values") or []:
        if f.get("field_code") == "PHONE":
            for v in f.get("values") or []:
                ph = norm_phone(str(v.get("value", "")))
                if ph:
                    return ph
    return ""


class AmoAdapter:
    name = "amocrm"
    fields = NAME_PHONE

    def __init__(self, amo):
        self.amo = amo
        self._names: dict[str, str] = {}

    async def _find(self, p: Person):
        cid = p.ext.get("amocrm")
        if cid:
            return await asyncio.to_thread(self.amo.get_contact_details, int(cid))
        if p.phone:
            return await asyncio.to_thread(self.amo.get_contact_by_phone, p.phone)
        return None

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        rows = {}
        for key, p in people.items():
            try:
                c = await self._find(p)
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] amocrm read %s: %s", key, exc)
                continue
            if not c or not c.get("id"):
                continue
            p.ext["amocrm"] = str(c["id"])
            self._names[key] = c.get("name", "")
            first, last = split_name(c.get("name", ""))
            rows[key] = {"first_name": first, "last_name": last, "phone": _phone_of(c)}
        return rows

    def _patch(self, cid: str, p: Person, name: str) -> bool:
        self.amo._load_token()
        tags = [{"name": TAG}] + [{"name": c} for c in sorted(p.cohorts)]
        body: dict = {"name": name, "_embedded": {"tags": tags}}
        if p.phone:
            body["custom_fields_values"] = [
                {"field_code": "PHONE", "values": [{"value": p.phone, "enum_code": "MOB"}]}
            ]
        r = requests.patch(
            f"{self.amo.base_url}/api/v4/contacts/{cid}",
            headers=self.amo._get_headers(),
            json=body,
            timeout=30,
        )
        return r.status_code in (200, 201)

    async def _one(self, p: Person) -> bool:
        name = display_name(p, self._names.get(p.key, ""))
        cid = p.ext.get("amocrm")
        if not cid:
            new = await asyncio.to_thread(self.amo.create_contact, name, p.phone)
            if not new:
                return False
            p.ext["amocrm"] = str(new)
            return True
        return await asyncio.to_thread(self._patch, cid, p, name)

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.first_name or p.last_name):
                continue
            if not (p.phone or p.ext.get("amocrm")):
                continue
            try:
                res["ok" if await self._one(p) else "failed"] += 1
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] amocrm %s: %s", key, exc)
                res["failed"] += 1
        return res
