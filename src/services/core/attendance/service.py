"""Check-in/check-out holat mashinasi: created → location_ok → qr_ok → confirmed.

Owner qarori (2026-10-22): yuz tekshiruvi hozircha o'chiq; GPS+QR o'tsa avtomatik
tasdiq, shubhali GPS bo'lsa ``PENDING_REVIEW`` va owner'ga Telegram xabari.
Barcha vaqt server soatidan olinadi — mijoz yuborgan vaqt faqat GPS yangiligini baholaydi.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from src.services.core.attendance import audit, geofence as gf, qr_tokens as qr, repo, rules
from src.services.core.attendance.notifier import NullNotifier, ReviewNotifier, format_review

DEFAULT_SESSION_TTL_S = 300
_CONFIRM_EXTRA_SQL = ", status = ?, confirmed_at = ?"


class AttendanceError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Actor:
    employee_id: int
    name: str
    subject: str
    ip: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceService:
    def __init__(self, db, *, clock: Callable[[], datetime] = _utcnow,
                 notifier: ReviewNotifier | None = None, qr_secret: str | None = None,
                 shift: rules.Shift | None = None, calendar: rules.Calendar | None = None):
        self.db, self.clock = db, clock
        self.notifier = notifier or NullNotifier()
        self.qr_secret = qr_secret
        # shift berilsa (testlar) — hamma uchun shu; aks holda xodimning shaxsiy grafigi bazadan.
        self._use_db_shifts = shift is None
        self.shift = shift or rules.Shift()
        self.calendar = calendar or rules.Calendar()

    # ---- helpers ----
    async def _load(self, sid: str, actor: Actor):
        s = await repo.get_session(self.db, sid)
        if s is None or int(s["employee_id"]) != actor.employee_id:
            raise AttendanceError("session_not_found", 404)
        if s["state"] != "confirmed" and datetime.fromisoformat(s["expires_at"]) < self.clock():
            raise AttendanceError("session_expired", 410)
        return s

    async def _move(self, s, actor: Actor, to_state: str, expect: str,
                    extra_sql: str = "", extra: list | None = None) -> None:
        if s["state"] != expect:
            raise AttendanceError(f"invalid_state:{s['state']}", 409)
        ok = await repo.advance(self.db, s["id"], actor.employee_id, expect, to_state,
                                int(s["version"]), extra_sql, extra)
        if not ok:
            raise AttendanceError("concurrent_update", 409)

    async def _policy(self, branch_id: int) -> rules.Policy:
        p = await repo.policy(self.db, branch_id)
        if p is None:
            return rules.Policy()
        return rules.Policy(int(p["grace_minutes"]), int(p["early_leave_grace_minutes"]))

    async def _shift_for(self, employee_id: int, day: str) -> rules.Shift:
        return rules.shift_from_row(await repo.employee_shift(self.db, employee_id, day)) \
            if self._use_db_shifts else self.shift

    @staticmethod
    def _public(s) -> dict:
        return {"id": s["id"], "kind": s["kind"], "state": s["state"], "work_date": s["work_date"],
                "expires_at": s["expires_at"], "required": ["gps", "qr"]}

    # ---- 1. sessiya ----
    async def start(self, actor: Actor, kind: str, idempotency_key: str) -> dict:
        if kind not in ("check_in", "check_out"):
            raise AttendanceError("invalid_kind", 422)
        if not 8 <= len(idempotency_key or "") <= 128:
            raise AttendanceError("idempotency_key_required", 422)
        existing = await repo.session_by_idem(self.db, idempotency_key)
        if existing is not None:
            if int(existing["employee_id"]) != actor.employee_id:
                raise AttendanceError("idempotency_key_conflict", 409)
            return self._public(existing)

        fence = await repo.active_geofence(self.db)
        if fence is None:
            raise AttendanceError("geofence_not_configured", 503)
        now = self.clock()
        work_date = rules.resolve_work_date(self.shift, now).isoformat()
        if await repo.confirmed_exists(self.db, actor.employee_id, work_date, kind):
            raise AttendanceError("already_recorded", 409)
        if kind == "check_out" and not await repo.confirmed_exists(
                self.db, actor.employee_id, work_date, "check_in"):
            raise AttendanceError("check_in_required", 409)

        s = {
            "id": secrets.token_urlsafe(18), "employee_id": actor.employee_id,
            "branch_id": int(fence["branch_id"]), "kind": kind, "work_date": work_date,
            "idempotency_key": idempotency_key, "state": "created",
            "expires_at": (now + timedelta(seconds=DEFAULT_SESSION_TTL_S)).isoformat(),
        }
        await repo.insert_session(self.db, s)
        await audit.log(self.db, actor=actor.subject, action="session_start", entity="attendance_session",
                        entity_id=s["id"], details={"kind": kind}, ip=actor.ip)
        await self.db.commit()
        return self._public(s)

    # ---- 2. GPS ----
    async def submit_location(self, sid: str, actor: Actor, fix: gf.LocationFix) -> dict:
        s = await self._load(sid, actor)
        if s["state"] != "created":
            raise AttendanceError(f"invalid_state:{s['state']}", 409)
        row = await repo.active_geofence(self.db, int(s["branch_id"]))
        if row is None:
            raise AttendanceError("geofence_not_configured", 503)
        fence = gf.Geofence(float(row["latitude"]), float(row["longitude"]),
                            int(row["radius_m"]), int(row["max_accuracy_m"]))
        result = gf.evaluate(fence, fix, self.clock(), await self._previous_fix(actor.employee_id))
        details = {"lat": round(fix.latitude, 6), "lon": round(fix.longitude, 6), "acc": fix.accuracy_m,
                   "captured_at": fix.captured_at.isoformat(), "distance_m": result.distance_m,
                   "risk": result.risk_score, "reasons": result.reasons, "review": result.needs_review}
        await repo.add_verification(self.db, sid, "gps", result.passed, result.risk_score,
                                    ",".join(result.reasons), details)
        # Aniq "hududdan tashqarida" — rad; shubhali (soxta GPS, past aniqlik) — davom etadi, lekin tekshiruvga.
        proceed = result.passed or result.needs_review
        if proceed:
            await self._move(s, actor, "location_ok", "created")
        await audit.log(self.db, actor=actor.subject, action="gps_submitted", entity="attendance_session",
                        entity_id=sid, details={"passed": result.passed, "reasons": result.reasons},
                        ip=actor.ip)
        await self.db.commit()
        if not proceed:
            raise AttendanceError("outside_geofence", 403)
        return {"passed": result.passed, "needs_review": result.needs_review,
                "distance_m": result.distance_m, "reasons": result.reasons}

    async def _previous_fix(self, employee_id: int) -> gf.PreviousFix | None:
        r = await repo.last_gps_fix(self.db, employee_id)
        if r is None:
            return None
        try:
            d = json.loads(r["details"])
            return gf.PreviousFix(float(d["lat"]), float(d["lon"]), datetime.fromisoformat(d["captured_at"]))
        except (KeyError, TypeError, ValueError):
            return None

    # ---- 3. QR ----
    async def submit_qr(self, sid: str, actor: Actor, token: str) -> dict:
        s = await self._load(sid, actor)
        if s["state"] != "location_ok":
            raise AttendanceError(f"invalid_state:{s['state']}", 409)
        try:
            claims = qr.verify(token, int(s["branch_id"]), self.clock(), secret=self.qr_secret)
            await qr.redeem(self.db, claims, actor.employee_id, sid)
        except qr.QrError as e:
            await repo.add_verification(self.db, sid, "qr", False, None, e.code, {})
            await self.db.commit()
            raise AttendanceError(f"qr_{e.code}", 503 if e.code == "not_configured" else 403) from None
        await repo.add_verification(self.db, sid, "qr", True, None, "", {"kiosk": claims.kiosk_id})
        await self._move(s, actor, "qr_ok", "location_ok")
        await self.db.commit()
        return {"passed": True}

    # ---- soddalashtirilgan oqim: GPS + ofis Wi-Fi (owner, 2026-10-22) ----
    async def punch(self, actor: Actor, kind: str, idempotency_key: str, fix: gf.LocationFix,
                    on_office_wifi: bool | None) -> dict:
        """Bir bosishda: sessiya → GPS → Wi-Fi → tasdiq.

        ``on_office_wifi=None`` — ofis Wi-Fi hali sozlanmagan, faqat GPS tekshiriladi.
        """
        if on_office_wifi is False:
            raise AttendanceError("not_on_office_wifi", 403)
        s = await self.start(actor, kind, idempotency_key)
        if s["state"] == "confirmed":
            row = await repo.get_session(self.db, s["id"])
            return {"status": row["status"], "already_confirmed": True, "work_date": s["work_date"]}
        if s["state"] == "created":
            await self.submit_location(s["id"], actor, fix)
        row = await repo.get_session(self.db, s["id"])
        if row["state"] == "location_ok":
            await repo.add_verification(self.db, s["id"], "manual", True, None, "office_wifi",
                                        {"wifi": on_office_wifi})
            await self._move(row, actor, "qr_ok", "location_ok")
            await self.db.commit()
        return await self.confirm(s["id"], actor)

    async def auto_punch(self, actor: Actor, kind: str, idempotency_key: str, method: str) -> dict:
        """Avtomatik belgi (Telegram jonli lokatsiya yoki ofis Wi-Fi avtomatikasi).

        Hudud tekshiruvini chaqiruvchi qilgan. Koordinatalar saqlanmaydi: tekshiruv
        yozuvida faqat usul nomi bo'ladi.
        """
        s = await self.start(actor, kind, idempotency_key)
        if s["state"] == "confirmed":
            row = await repo.get_session(self.db, s["id"])
            return {"status": row["status"], "already_confirmed": True, "work_date": s["work_date"]}
        row = await repo.get_session(self.db, s["id"])
        if row["state"] == "created":
            await repo.add_verification(self.db, s["id"], "manual", True, None, method, {"auto": method})
            await self._move(row, actor, "location_ok", "created")
            row = await repo.get_session(self.db, s["id"])
        if row["state"] == "location_ok":
            await self._move(row, actor, "qr_ok", "location_ok")
        await audit.log(self.db, actor=actor.subject, action="auto_punch", entity="attendance_session",
                        entity_id=s["id"], details={"kind": kind, "method": method}, ip=actor.ip)
        await self.db.commit()
        return await self.confirm(s["id"], actor)

    # ---- 4. yuz (hozircha o'chiq) ----
    async def submit_face(self, sid: str, actor: Actor) -> dict:
        await self._load(sid, actor)
        raise AttendanceError("face_verification_disabled", 501)

    # ---- 5. tasdiq ----
    async def confirm(self, sid: str, actor: Actor) -> dict:
        s = await self._load(sid, actor)
        if s["state"] == "confirmed":
            return {"status": s["status"], "already_confirmed": True, "work_date": s["work_date"]}
        now = self.clock()
        pol = await self._policy(int(s["branch_id"]))
        classify = rules.classify_check_in if s["kind"] == "check_in" else rules.classify_check_out
        shift = await self._shift_for(actor.employee_id, s["work_date"])
        c = classify(shift, pol, self.calendar, now)
        review = self._review_reasons(await repo.verifications(self.db, sid)) + c.notes
        status = rules.PENDING_REVIEW if review else c.status
        try:
            # UNIQUE(employee, work_date, kind) WHERE confirmed — parallel ikkinchi tasdiq shu yerda to'xtaydi.
            await self._move(s, actor, "confirmed", "qr_ok", _CONFIRM_EXTRA_SQL, [status, now.isoformat()])
            await repo.insert_event(self.db, {
                "session_id": s["id"], "employee_id": actor.employee_id, "branch_id": int(s["branch_id"]),
                "kind": s["kind"], "work_date": s["work_date"], "server_ts": now.isoformat(),
                "status": status, "minutes_late": c.minutes_late, "minutes_early": c.minutes_early,
                "verification_summary": {"gps": True, "second_factor": "qr_or_wifi", "face": "disabled",
                                         "review": review},
            })
            await audit.log(self.db, actor=actor.subject, action="attendance_confirmed",
                            entity="attendance_session", entity_id=s["id"], details={"status": status},
                            ip=actor.ip)
            await self.db.commit()
        except AttendanceError:
            raise
        except Exception as exc:
            await self.db.rollback()
            if "UNIQUE" in str(exc).upper():
                raise AttendanceError("already_recorded", 409) from None
            raise
        if status == rules.PENDING_REVIEW:
            local = now.astimezone(ZoneInfo(self.shift.timezone)).strftime("%H:%M")
            await self.notifier.notify_review(format_review(actor.name, s["kind"], local, review))
        return {"status": status, "minutes_late": c.minutes_late, "minutes_early": c.minutes_early,
                "server_ts": now.isoformat(), "work_date": s["work_date"]}

    @staticmethod
    def _review_reasons(checks) -> list[str]:
        reasons: list[str] = []
        for row in checks:
            if row["method"] == "gps":
                d = json.loads(row["details"] or "{}")
                if d.get("review"):
                    reasons.extend(d.get("reasons") or ["gps_review"])
        return reasons
