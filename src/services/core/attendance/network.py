"""Ofis Wi-Fi tekshiruvi: so'rov ofis internetining tashqi IP manzilidan kelganmi.

Brauzer Wi-Fi nomini (SSID) o'qiy olmaydi, shuning uchun ofis routerining public IP si
ishlatiladi. Owner ofis Wi-Fi'siga ulangan holda "Ofis Wi-Fi'ni belgilash" ni bosadi — o'sha
IP saqlanadi. Mijoz IP faqat lokal proxy (Nginx) bergan sarlavhadan olinadi; aniqlanmasa
yoki xususiy/loopback bo'lsa — fail-closed (ofisdan emas deb hisoblanadi).
"""
from __future__ import annotations

import ipaddress

from src.services.core.attendance import audit, repo
from src.services.core.attendance.service import AttendanceError

_TRUSTED_PROXIES = frozenset({"127.0.0.1", "::1"})


def client_ip(request) -> str | None:
    peer = request.client.host if request.client else ""
    if peer in _TRUSTED_PROXIES:
        candidate = (request.headers.get("X-Real-IP") or "").strip()
        if not candidate:
            fwd = request.headers.get("X-Forwarded-For", "")
            candidate = fwd.split(",")[-1].strip() if fwd else ""
    else:
        candidate = peer
    return candidate if is_public(candidate) else None


def is_public(ip: str | None) -> bool:
    try:
        return bool(ip) and ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


async def configured(db) -> bool:
    return bool(await repo.one(db, "SELECT 1 FROM attendance_office_networks WHERE revoked_at IS NULL", []))


async def is_office(db, ip: str | None) -> bool:
    if not ip:
        return False
    return bool(await repo.one(db, "SELECT 1 FROM attendance_office_networks WHERE ip = ? AND revoked_at IS NULL",
                               [ip]))


async def add(db, *, actor: str, ip: str | None, label: str) -> dict:
    if not is_public(ip):
        raise AttendanceError("office_ip_unknown", 422)
    await db.execute(
        "INSERT INTO attendance_office_networks (ip, label, created_by) VALUES (?, ?, ?)"
        " ON CONFLICT (ip) DO UPDATE SET revoked_at = NULL, label = excluded.label", [ip, label, actor])
    await audit.log(db, actor=actor, action="office_network_set", entity="office_network", entity_id=ip)
    await db.commit()
    return {"ip": ip, "label": label}


async def list_all(db) -> list[dict]:
    rows = await db.execute("SELECT id, ip, label, created_at FROM attendance_office_networks"
                            " WHERE revoked_at IS NULL ORDER BY id", [])
    return [{"id": r["id"], "ip": r["ip"], "label": r["label"], "created_at": r["created_at"]} for r in rows]


async def remove(db, *, actor: str, network_id: int) -> bool:
    rows = await db.execute("UPDATE attendance_office_networks SET revoked_at = CURRENT_TIMESTAMP"
                            " WHERE id = ? AND revoked_at IS NULL RETURNING id", [network_id])
    if rows:
        await audit.log(db, actor=actor, action="office_network_removed", entity="office_network",
                        entity_id=network_id)
    await db.commit()
    return bool(rows)
