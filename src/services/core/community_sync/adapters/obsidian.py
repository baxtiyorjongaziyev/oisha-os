"""Second brain (Obsidian vault) adapteri: har mijoz uchun bitta karta.

Karta: <vault>/60-Wiki/mijozlar/<Ism Familya>.md. Frontmatter sinxron maydonlarni
va boshqa tizimlardagi ID larni saqlaydi; tanasi (qöl yozuvlar) hech qachon özgarmaydi.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from ..models import Person, display_name, labels_for
from .base import NAME_PHONE, keys_of, norm_phone, result

logger = logging.getLogger(__name__)
FOLDER = Path("60-Wiki") / "mijozlar"
_FM_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
_ID_KEYS = ("google", "amocrm", "airtable")


def _parse(text: str) -> tuple[dict[str, str], str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():]


def _q(v) -> str:
    return '"' + str(v or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render(p: Person, body: str) -> str:
    lines = [
        "---",
        "type: mijoz",
        f"key: {_q(p.key)}",
        f"name: {_q(display_name(p))}",
        f"first_name: {_q(p.first_name)}",
        f"last_name: {_q(p.last_name)}",
        f"phone: {_q(p.phone)}",
        f"username: {_q(p.username)}",
        f"tg_id: {_q(p.tg_id or '')}",
        f"company: {_q(p.company)}",
        f"activity: {_q(p.activity)}",
        f"region: {_q(p.region)}",
    ]
    lines += [f"{k}_id: {_q(p.ext.get(k, ''))}" for k in _ID_KEYS]
    lines.append("tags: [" + ", ".join(_q(t) for t in ["mijoz", *labels_for(p)]) + "]")
    lines.append("---")
    body = body if body.strip() else f"\n# {display_name(p)}\n\n## Izohlar\n"
    return "\n".join(lines) + "\n" + body


def _safe(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|#^\[\]]', "", name).strip() or "mijoz"


class ObsidianAdapter:
    name = "obsidian"
    fields = NAME_PHONE

    def __init__(self, vault: Optional[Path]):
        self.dir = Path(vault) / FOLDER if vault else None
        self._files: dict[str, Path] = {}

    def _scan(self) -> list[tuple[Path, dict[str, str]]]:
        if not self.dir:
            raise RuntimeError("vault topilmadi")
        self.dir.mkdir(parents=True, exist_ok=True)
        out = []
        for f in self.dir.glob("*.md"):
            meta, _ = _parse(f.read_text(encoding="utf-8"))
            if meta.get("type") == "mijoz":
                out.append((f, meta))
        return out

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        cards = await asyncio.to_thread(self._scan)
        by_key = {m.get("key"): (f, m) for f, m in cards if m.get("key")}
        by_phone = {norm_phone(m.get("phone", "")): (f, m) for f, m in cards}
        by_phone.pop("", None)
        rows = {}
        for key, p in people.items():
            hit = by_key.get(key) or (p.phone and by_phone.get(p.phone))
            if not hit:
                continue
            f, m = hit
            self._files[key] = f
            rows[key] = {
                "first_name": m.get("first_name", ""),
                "last_name": m.get("last_name", ""),
                "phone": norm_phone(m.get("phone", "")),
            }
        return rows

    def _write(self, p: Person) -> bool:
        path = self._files.get(p.key) or self.dir / f"{_safe(display_name(p))}.md"
        if path.exists() and p.key not in self._files:
            path = self.dir / f"{_safe(display_name(p))} {_safe(p.key)}.md"
        body = ""
        if path.exists():
            _, body = _parse(path.read_text(encoding="utf-8"))
        path.write_text(_render(p, body), encoding="utf-8")
        self._files[p.key] = path
        return True

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.first_name or p.phone):
                continue
            try:
                await asyncio.to_thread(self._write, p)
                res["ok"] += 1
                res["keys"].append(key)
                res["written"][key] = {
                    "first_name": p.first_name, "last_name": p.last_name, "phone": p.phone,
                }
            except Exception as exc:
                logger.error("[COMMUNITY_SYNC] obsidian %s: %s", key, exc)
                res["failed"] += 1
        return res
