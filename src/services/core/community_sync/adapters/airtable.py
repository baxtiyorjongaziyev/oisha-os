"""Airtable "Mijozlar" jadvali adapteri (mavjud AirtableSync._request orqali).

Ism bitta maydonda ("Mijoz ismi") saqlanadi: kanonik "Ism Familya <suffix>" yoziladi.
Mavjud yozuvlar faqat yangilanadi; yangi yozuv faqat telefon bor shaxs uchun yaratiladi.
"""

import asyncio
import logging

from ..models import Person, display_name, name_locked
from .base import NAME_PHONE, keys_of, norm_phone, result, split_name

logger = logging.getLogger(__name__)
TABLE = "tblYeFpWhQIMmrWPZ"
F_NAME = "Mijoz ismi"
F_PHONE = "Telefon raqami"


class AirtableAdapter:
    name = "airtable"
    fields = NAME_PHONE

    def __init__(self, airtable, table: str = TABLE):
        self.at = airtable
        self.url = airtable._table_url(table)
        self._names: dict[str, str] = {}

    def _list(self) -> list[dict]:
        out, offset = [], None
        while True:
            params = {"pageSize": 100, "fields[]": [F_NAME, F_PHONE]}
            if offset:
                params["offset"] = offset
            r = self.at._request("GET", self.url, params=params)
            if r.status_code != 200:
                raise RuntimeError(f"airtable list: HTTP {r.status_code}")
            data = r.json()
            out += data.get("records", [])
            offset = data.get("offset")
            if not offset:
                return out

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        records = await asyncio.to_thread(self._list)
        by_id = {r["id"]: r for r in records}
        by_phone: dict[str, dict] = {}
        for r in records:
            ph = norm_phone(str(r.get("fields", {}).get(F_PHONE, "")))
            if ph:
                by_phone.setdefault(ph, r)
        rows = {}
        for key, p in people.items():
            rec = by_id.get(p.ext.get("airtable", "")) or (p.phone and by_phone.get(p.phone))
            if not rec:
                continue
            p.ext["airtable"] = rec["id"]
            f = rec.get("fields", {})
            full = str(f.get(F_NAME, "") or "")
            self._names[key] = full
            row = {"phone": norm_phone(str(f.get(F_PHONE, "")))}
            if name_locked(p, full):
                row.update(first_name=p.first_name, last_name=p.last_name)
            else:
                first, last = split_name(full)
                row.update(first_name=first, last_name=last)
            rows[key] = row
        return rows

    def _write(self, p: Person) -> bool:
        fields = {F_NAME: display_name(p, self._names.get(p.key, ""))}
        if p.phone:
            fields[F_PHONE] = p.phone
        rid = p.ext.get("airtable")
        if rid:
            r = self.at._request("PATCH", f"{self.url}/{rid}", json={"fields": fields, "typecast": True})
        else:
            if not p.phone:
                return False
            r = self.at._request("POST", self.url, json={"fields": fields, "typecast": True})
            if r.status_code == 200:
                p.ext["airtable"] = r.json().get("id", "")
        return r.status_code == 200

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.first_name or p.phone):
                continue
            try:
                if await asyncio.to_thread(self._write, p):
                    res["ok"] += 1
                    res["keys"].append(key)
                    res["written"][key] = {
                        "first_name": p.first_name, "last_name": p.last_name, "phone": p.phone,
                    }
                else:
                    res["failed"] += 1
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] airtable %s: %s", key, exc)
                res["failed"] += 1
        return res
