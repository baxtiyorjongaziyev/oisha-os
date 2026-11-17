"""Google Contacts adapteri (People API, mavjud GoogleContactsSync orqali)."""

import asyncio
import logging

from ..models import Person, display_name, labels_for
from .base import NAME_PHONE, keys_of, norm_phone, result, split_name

logger = logging.getLogger(__name__)


class GoogleAdapter:
    name = "google"
    fields = NAME_PHONE

    def __init__(self, gcontacts):
        self.g = gcontacts
        self._display: dict[str, str] = {}

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        contacts = await asyncio.to_thread(self.g.list_all_contacts)
        by_res = {c["resource_name"]: c for c in contacts}
        by_phone: dict[str, dict] = {}
        for c in contacts:
            for ph in c.get("phones", []):
                by_phone.setdefault(norm_phone(ph), c)
        by_phone.pop("", None)
        rows = {}
        for key, p in people.items():
            c = by_res.get(p.ext.get("google", "")) or (p.phone and by_phone.get(p.phone))
            if not c:
                continue
            p.ext["google"] = c["resource_name"]
            self._display[key] = c.get("display_name", "")
            first, last = split_name(f"{c.get('given_name', '')} {c.get('family_name', '')}")
            phones = [norm_phone(x) for x in c.get("phones", [])]
            rows[key] = {
                "first_name": first,
                "last_name": last,
                "phone": next((x for x in phones if x), ""),
            }
        return rows

    def _name_parts(self, p: Person, existing: str) -> tuple[str, str]:
        full = display_name(p, existing)
        first = p.first_name if p.first_name and full.startswith(p.first_name) else full.split(" ", 1)[0]
        return first, full[len(first):].strip()

    async def _one(self, p: Person) -> bool:
        resource = p.ext.get("google")
        phones = [p.phone] if p.phone else []
        first, last = self._name_parts(p, self._display.get(p.key, ""))
        if not resource:
            new = await asyncio.to_thread(
                self.g.create_person, first, last, phones, labels_for(p)
            )
            if new:
                p.ext["google"] = new
            return bool(new)
        ok = await asyncio.to_thread(self.g.update_person, resource, first, last, phones)
        for label in labels_for(p):
            await asyncio.to_thread(self.g.add_to_group, resource, label)
        return bool(ok)

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.first_name or p.phone):
                continue
            try:
                res["ok" if await self._one(p) else "failed"] += 1
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] google %s: %s", key, exc)
                res["failed"] += 1
        return res
