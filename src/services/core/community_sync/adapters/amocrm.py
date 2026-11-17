"""AmoCRM kontakt adapteri (mavjud AmoCRM klienti orqali).

Telefon va teglar faqat QÖSHILADI: v4 PATCH toʻplamni almashtirgani uchun
mavjudlari ham yuboriladi.
"""

import asyncio
import logging

import requests

from ..models import Person, display_name, name_locked
from .base import NAME_PHONE, keys_of, norm_phone, result, split_name

logger = logging.getLogger(__name__)
TAG = "community"


def _phones_of(contact: dict) -> list[str]:
    out = []
    for f in contact.get("custom_fields_values") or []:
        if f.get("field_code") == "PHONE":
            out += [norm_phone(str(v.get("value", ""))) for v in f.get("values") or []]
    return [x for x in out if x]


def _tags_of(contact: dict) -> list[str]:
    tags = (contact.get("_embedded") or {}).get("tags") or []
    return [t.get("name") for t in tags if t.get("name")]


class AmoAdapter:
    name = "amocrm"
    fields = NAME_PHONE

    def __init__(self, amo):
        self.amo = amo
        self._contacts: dict[str, dict] = {}
        self.failed_reads: set[str] = set()

    async def _find(self, p: Person):
        cid = p.ext.get("amocrm")
        if cid:
            return await asyncio.to_thread(self.amo.get_contact_details, int(cid))
        if not p.phone:
            return None
        c = await asyncio.to_thread(self.amo.get_contact_by_phone, p.phone)
        # Qidiruv substring boʻyicha: telefon aniq mos kelmasa, begona kontakt olinmaydi
        return c if c and p.phone in _phones_of(c) else None

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        rows = {}
        for key, p in people.items():
            try:
                c = await self._find(p)
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] amocrm read %s: %s", key, exc)
                self.failed_reads.add(key)
                continue
            if not c or not c.get("id"):
                continue
            p.ext["amocrm"] = str(c["id"])
            self._contacts[key] = c
            phones = _phones_of(c)
            row = {"phone": p.phone if p.phone in phones else (phones[0] if phones else "")}
            if name_locked(p, c.get("name", "")):
                row.update(first_name=p.first_name, last_name=p.last_name)
            else:
                first, last = split_name(c.get("name", ""))
                row.update(first_name=first, last_name=last)
            rows[key] = row
        return rows

    def _patch(self, cid: str, p: Person, current: dict) -> bool:
        name = display_name(p, current.get("name", ""))
        phones = _phones_of(current)
        tags = _tags_of(current)
        want_tags = tags + [t for t in [TAG] + sorted(p.cohorts) if t not in tags]
        body: dict = {}
        if name != current.get("name"):
            body["name"] = name
        if want_tags != tags:
            body["_embedded"] = {"tags": [{"name": t} for t in want_tags]}
        if p.phone and p.phone not in phones:
            vals = [{"value": x, "enum_code": "MOB"} for x in phones + [p.phone]]
            body["custom_fields_values"] = [{"field_code": "PHONE", "values": vals}]
        if not body:
            return True
        self.amo._load_token()
        r = requests.patch(
            f"{self.amo.base_url}/api/v4/contacts/{cid}",
            headers=self.amo._get_headers(),
            json=body,
            timeout=30,
        )
        return r.status_code in (200, 201)

    async def _one(self, p: Person) -> bool:
        cid = p.ext.get("amocrm")
        current = self._contacts.get(p.key, {})
        if not cid:
            new = await asyncio.to_thread(self.amo.create_contact, display_name(p), p.phone)
            if not new:
                return False
            cid = p.ext["amocrm"] = str(new)
            current = {"name": display_name(p), "custom_fields_values": [
                {"field_code": "PHONE", "values": [{"value": p.phone}]}]}
        return await asyncio.to_thread(self._patch, cid, p, current)

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if key in self.failed_reads or not p or not (p.first_name or p.last_name):
                continue
            if not (p.phone or p.ext.get("amocrm")):
                continue
            try:
                if await self._one(p):
                    res["ok"] += 1
                    res["keys"].append(key)
                    res["written"][key] = {f: getattr(p, f) for f in self.fields}
                else:
                    res["failed"] += 1
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] amocrm %s: %s", key, exc)
                res["failed"] += 1
        return res
