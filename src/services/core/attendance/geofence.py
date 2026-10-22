"""GPS tekshiruvi: geofence ichidami, aniqlik va vaqt yetarlimi, soxta GPS xavfi.

Lokatsiya faqat check-in/check-out paytida bir marta yuboriladi; bu modul hech
narsani kuzatmaydi va saqlamaydi — natijani chaqiruvchi tomon yozadi.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

EARTH_RADIUS_M = 6_371_000
MAX_CLOCK_SKEW_S = 120
# Odam piyoda/transportda bu tezlikdan oshmaydi; oshsa — "teleport" (soxta GPS belgisi).
MAX_PLAUSIBLE_SPEED_MPS = 70
REVIEW_RISK_THRESHOLD = 0.5


@dataclass(frozen=True)
class Geofence:
    latitude: float
    longitude: float
    radius_m: int
    max_accuracy_m: int = 50


@dataclass(frozen=True)
class LocationFix:
    latitude: float
    longitude: float
    accuracy_m: float
    captured_at: datetime
    is_mocked: bool | None = None  # faqat native ilova bera oladi; brauzer — None


@dataclass(frozen=True)
class PreviousFix:
    latitude: float
    longitude: float
    captured_at: datetime


@dataclass
class GeofenceResult:
    passed: bool
    distance_m: float
    risk_score: float
    needs_review: bool
    reasons: list[str] = field(default_factory=list)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _valid_coords(fix: LocationFix) -> bool:
    return (
        -90 <= fix.latitude <= 90
        and -180 <= fix.longitude <= 180
        and math.isfinite(fix.accuracy_m)
        and fix.accuracy_m >= 0
    )


def _spoof_risk(fix: LocationFix, now: datetime, previous: PreviousFix | None) -> tuple[float, list[str]]:
    risk, reasons = 0.0, []
    if fix.is_mocked:
        risk += 1.0
        reasons.append("mock_location_flag")
    if fix.accuracy_m == 0:
        risk += 0.6
        reasons.append("zero_accuracy")
    if previous is not None:
        dt = (fix.captured_at - previous.captured_at).total_seconds()
        dist = haversine_m(previous.latitude, previous.longitude, fix.latitude, fix.longitude)
        if dt > 0 and dist / dt > MAX_PLAUSIBLE_SPEED_MPS:
            risk += 0.6
            reasons.append("impossible_travel")
    return min(risk, 1.0), reasons


def evaluate(
    fence: Geofence,
    fix: LocationFix,
    now: datetime,
    previous: PreviousFix | None = None,
) -> GeofenceResult:
    """GPS ni baholaydi. ``passed=False`` bo'lsa davomat avtomatik tasdiqlanmaydi."""
    if not _valid_coords(fix):
        return GeofenceResult(False, float("nan"), 1.0, True, ["invalid_coordinates"])

    distance = haversine_m(fence.latitude, fence.longitude, fix.latitude, fix.longitude)
    risk, reasons = _spoof_risk(fix, now, previous)

    skew = abs((now - fix.captured_at).total_seconds())
    if skew > MAX_CLOCK_SKEW_S:
        reasons.append("stale_or_future_timestamp")
    if fix.accuracy_m > fence.max_accuracy_m:
        reasons.append("low_accuracy")
    # Aniqlik doirasi ham fence ichida bo'lishi kerak — chegaradagi "balki ichida" o'tmaydi.
    if distance + min(fix.accuracy_m, fence.max_accuracy_m) > fence.radius_m:
        reasons.append("outside_geofence")

    hard_fail = {"stale_or_future_timestamp", "low_accuracy", "outside_geofence"} & set(reasons)
    passed = not hard_fail and risk < REVIEW_RISK_THRESHOLD
    needs_review = not passed and not ("outside_geofence" in reasons and risk == 0)
    return GeofenceResult(passed, round(distance, 1), risk, needs_review, reasons)
