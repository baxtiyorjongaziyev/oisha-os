"""AI ROP CEO traffic light. Pure."""
from __future__ import annotations

from dataclasses import dataclass

from src.services.core.rop.discipline import Finding


@dataclass
class SellerMetrics:
    won_today: int
    no_result_streak_days: int
    overdue_count: int
    calls_done: int
    calls_target: int
    follow_ups_done: int
    follow_ups_target: int
    meetings_done: int
    meetings_target: int
    biggest_stuck_deal_amount: int
    biggest_stuck_deal_days: float
    hot_lead_max_silent_hours: float
    hot_band_dropped: bool


@dataclass(frozen=True)
class TrafficResult:
    level: str
    reasons: list[str]


def evaluate(metrics: SellerMetrics, findings: list[Finding], config: dict) -> TrafficResult:
    red: list[str] = []
    if metrics.won_today == 0 and metrics.no_result_streak_days >= config["traffic.red_no_result_days"]:
        red.append(f"{metrics.no_result_streak_days} ish kuni natijasiz")
    if metrics.overdue_count >= config["traffic.red_overdue_count"]:
        red.append(f"{metrics.overdue_count} ta muddati o'tgan task")
    if (metrics.biggest_stuck_deal_amount >= config["traffic.big_deal_amount"]
            and metrics.biggest_stuck_deal_days >= config["traffic.stuck_deal_days"]):
        red.append("Katta bitim uzoq vaqt qotib qolgan")
    if len(findings) >= config["traffic.red_discipline_count"]:
        red.append(f"{len(findings)} ta CRM intizom buzilishi")
    if red:
        return TrafficResult("RED", red)

    yellow: list[str] = []
    yp = config["traffic.yellow_pace_pct"]
    if metrics.calls_target > 0 and metrics.calls_done < yp * metrics.calls_target:
        yellow.append("Qo'ng'iroqlar sur'ati past")
    if metrics.meetings_target > 0 and metrics.meetings_done < yp * metrics.meetings_target:
        yellow.append("Uchrashuvlar sur'ati past")
    if metrics.follow_ups_target > 0 and metrics.follow_ups_done < 0.5 * metrics.follow_ups_target:
        yellow.append("Follow-up orqada")
    if metrics.hot_lead_max_silent_hours >= config["traffic.hot_lead_silent_hours"]:
        yellow.append("Issiq mijoz javobsiz qolgan")
    if metrics.hot_band_dropped:
        yellow.append("Issiq bitim ehtimoli tushdi")
    if yellow:
        return TrafficResult("YELLOW", yellow)

    return TrafficResult("GREEN", [])
