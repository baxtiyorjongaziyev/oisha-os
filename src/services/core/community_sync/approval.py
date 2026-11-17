"""Owner tasdigʻi: katta yozuvlar uchun ruxsat va konflikt tanlash tugmalari.

Callback maʼlumoti: "cs:approve" yoki "cs:pick:<key>:<field>:<system>".
Botga ulash (boot.py) Coordinator ishi: handle_callback(data, store) chaqiriladi.
"""

from datetime import datetime, timedelta

from .merge import Conflict

APPROVE_KEY = "community_sync:approved_until"
APPROVE_DATA = "cs:approve"
APPROVAL_TTL = timedelta(hours=24)


def approval_buttons() -> list[tuple[str, str]]:
    return [("✅ Tasdiqlash", APPROVE_DATA)]


def conflict_buttons(c: Conflict) -> list[tuple[str, str]]:
    return [
        (f"{system}: {value}"[:40], f"cs:pick:{c.key}:{c.field}:{system}")
        for system, value in sorted(c.values.items())
    ]


def conflict_text(c: Conflict) -> str:
    lines = [f"Konflikt: {c.key} — {c.field}"]
    lines += [f"• {s}: {v}" for s, v in sorted(c.values.items())]
    lines.append("Qaysi qiymat tögʻri?")
    return "\n".join(lines)


async def is_approved(store, now: datetime) -> bool:
    until = await store.get_state(APPROVE_KEY)
    return bool(until) and datetime.fromisoformat(until) >= now


async def handle_callback(data: str, store, now: datetime) -> bool:
    if data == APPROVE_DATA:
        await store.set_state(APPROVE_KEY, (now + APPROVAL_TTL).isoformat(timespec="seconds"))
        return True
    if not data.startswith("cs:pick:"):
        return False
    parts = data[len("cs:pick:"):].rsplit(":", 2)
    if len(parts) != 3:
        return False
    key, field, system = parts
    for c in await store.open_conflicts():
        if c.key == key and c.field == field and system in c.values:
            await store.resolve_conflict(key, field, c.values[system])
            return True
    return False
