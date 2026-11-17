"""Google Contacts adapteri (People API, mavjud GoogleContactsSync orqali)."""

import asyncio
import logging

from ..models import Person, display_name, labels_for, name_locked
from .base import NAME_PHONE, keys_of, norm_phone, result, split_name

logger = logging.getLogger(__name__)


class GoogleAdapter:
    name = "google"
    fields = NAME_PHONE

    def __init__(self, gcontacts):
        self.g = gcontacts
        self._display: dict[str, str] = {}
        self._phones: dict[str, list[str]] = {}

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        # Xato boʻsh roʻyxat sifatida yutilmaydi: aks holda hamma uchun dublikat yaratiladi
        contacts = await asyncio.to_thread(self.g.list_all_contacts, True)
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
            rows[key] = self._row(key, p, c)
        return rows

    def _row(self, key: str, p: Person, c: dict) -> dict[str, str]:
        p.ext["google"] = c["resource_name"]
        self._display[key] = c.get("display_name", "")
        phones = [x for x in (norm_phone(v) for v in c.get("phones", [])) if x]
        self._phones[key] = phones
        row = {"phone": p.phone if p.phone in phones else (phones[0] if phones else "")}
        if name_locked(p, self._display[key]):
            # Boshqa kohort suffiksli nom: ism bu tizimda boshqarilmaydi
            row.update(first_name=p.first_name, last_name=p.last_name)
        else:
            first, last = split_name(f"{c.get('given_name', '')} {c.get('family_name', '')}")
            row.update(first_name=first, last_name=last)
        return row

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
            ok = await asyncio.to_thread(self.g.add_to_group, resource, label) and ok
        return bool(ok)

    def _written(self, p: Person) -> dict[str, str]:
        """Snapshot = tizimda haqiqatda turgan qiymat (locked nomda ham kanonik deb öqiladi)."""
        return {"first_name": p.first_name, "last_name": p.last_name, "phone": p.phone}

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.first_name or p.phone):
                continue
            try:
                if await self._one(p):
                    res["ok"] += 1
                    res["keys"].append(key)
                    res["written"][key] = self._written(p)
                else:
                    res["failed"] += 1
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] google %s: %s", key, exc)
                res["failed"] += 1
        return res
