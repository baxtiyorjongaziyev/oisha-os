"""AI ROP message templates — Uzbek (Latin), HTML, deterministic. No LLM."""
from __future__ import annotations

from html import escape

from src.services.core.rop.daily import (
    CeoDashboard, CeoMidday, CeoMorning, SellerEveningResult, SellerMiddayCheck,
    SellerMorningPlan,
)
from src.services.core.rop.scoring import DISCLAIMER
from src.services.core.rop.weekly import WeeklyProgress

_BAND_UZ = {"HOT": "issiq", "WARM": "iliq", "COLD": "sovuq"}
_MAX_LIST = 5


def fmt_sum(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def progress_bar(pct: float, width: int = 10) -> str:
    fill = round(min(max(pct, 0.0), 100.0) / 100 * width)
    return "\U00002588" * fill + "\U00002591" * (width - fill)


def _trim(items: list[str]) -> list[str]:
    if len(items) <= _MAX_LIST:
        return items
    return items[:_MAX_LIST] + [f"+{len(items) - _MAX_LIST} ta yana"]


def _weekly_line(w: WeeklyProgress) -> str:
    return (
        f"Haftalik: {w.won_count}/{w.sales_target} sotuv "
        f"({w.sales_pct:.0f}%)  [{progress_bar(w.sales_pct)}]\n"
        f"Revenue: {fmt_sum(w.won_revenue)} / {fmt_sum(w.revenue_target)} so'm"
    )


def render_seller_morning(plan: SellerMorningPlan) -> str:
    s = plan.seller
    lines = [f"<b>Bugungi plan — {s.expected_sales} ta sotuv</b>", ""]
    if plan.top_closings:
        lines.append("\U0001F525 <b>Closingga eng yaqin:</b>")
        for i, ls in enumerate(plan.top_closings, 1):
            reason = ls.reasons[0] if ls.reasons else _BAND_UZ.get(ls.band, "")
            lines.append(
                f"{i}. {escape(ls.name)} — {escape(reason)} → <i>{escape(ls.action)}</i>"
            )
        lines.append("")
    lines.append("<b>Bugun:</b>")
    lines.append(f"🎯 <b>Asosiy marra: {plan.solid_calls_target} ta sifatli suhbat (≥3 daqiqa)!</b>")
    lines.append(f"• {s.calls} ta qo'ng'iroq")
    lines.append(f"• {s.follow_ups} ta follow-up")
    lines.append(f"• {s.meetings} ta uchrashuv")
    lines.append(f"• {s.payments} ta to'lov")
    if plan.followup_due:
        lines.append("")
        lines.append("<b>Bugun follow-up:</b>")
        for n in _trim([escape(x) for x in plan.followup_due]):
            lines.append(f"• {n}")
    lines.append("")
    if plan.expected:
        lines.append("<b>Bugun kutilyapti:</b>")
        for e in _trim([
            f"{escape(e.name)} — {fmt_sum(e.revenue_est)} so'm — {e.score}%"
            for e in plan.expected
        ]):
            lines.append(f"• {e}")
        lines.append(f"Expected revenue: {fmt_sum(plan.expected_revenue_total)} so'm")
        lines.append(f"<i>{DISCLAIMER}</i>")
        lines.append("")
    if plan.overdue_tasks:
        lines.append(f"⚠️ <b>Overdue: {len(plan.overdue_tasks)} ta task</b>")
        for name, txt in plan.overdue_tasks[:_MAX_LIST]:
            lines.append(f"• {escape(name)}: {escape(txt)}")
        if len(plan.overdue_tasks) > _MAX_LIST:
            lines.append(f"+{len(plan.overdue_tasks) - _MAX_LIST} ta yana")
    if plan.discipline_findings:
        lines.append("")
        lines.append("⚠️ <b>CRM intizomi:</b>")
        seen = _trim([
            f"{escape(f.lead_name)} — {escape(_FINDING_UZ.get(f.type, f.type))}"
            for f in plan.discipline_findings
        ])
        for x in seen:
            lines.append(f"• {x}")
    return "\n".join(lines)


_FINDING_UZ = {
    "NO_NEXT_TASK": "keyingi task yo'q",
    "OVERDUE_TASK": "muddati o'tgan task",
    "STAGNANT": "uzoq vaqt harakatsiz",
    "NO_OWNER": "mas'ul biriktirilmagan",
    "WRONG_STAGE": "noto'g'ri bosqich",
    "IMPORTANT_NO_NOTE": "muhim aloqadan keyin izoh yo'q",
}


def render_seller_midday(check: SellerMiddayCheck) -> str:
    s = check.seller
    lines = [
        "<b>Tushki tekshiruv (14:00)</b>",
        "",
        f"Plan: {check.plan}",
        f"Fakt: {check.fakt}",
        "",
    ]
    if check.solid_calls > 0 or check.total_calls > 0:
        mins = check.talk_seconds // 60
        pct = round(check.solid_calls / check.solid_calls_target * 100) if check.solid_calls_target else 0
        lines.append("📞 <b>Qo'ng'iroqlar (Moizvonki):</b>")
        lines.append(f"• Sifatli suhbatlar (≥3 daq): <b>{check.solid_calls}/{check.solid_calls_target} ta</b> ({pct}%)")
        lines.append(f"• Jami qo'ng'iroqlar: {check.total_calls} ta (ko'tarilgan: {check.answered_calls})")
        lines.append(f"• Gaplashilgan vaqt: {mins} daqiqa")
        if check.solid_calls < 20:
            lines.append("⚠️ <i>Diqqat: Tushgacha marra 20-25 ta sifatli suhbat! Kechgacha 50 taga yetish uchun sur'atni oshiring!</i>")
        else:
            lines.append("🔥 <i>Ajoyib sur'at! Tushlik marrasi bajarildi. Kechgacha 50 taga yetkazishda davom eting!</i>")
        lines.append("")
    lines.extend([
        f"{check.calls_done}/{s.calls} CRM vazifa qo'ng'irog'i",
        f"{check.follow_ups_done}/{s.follow_ups} follow-up",
        f"{check.meetings_done}/{s.meetings} uchrashuv",
    ])
    if check.hot_not_touched:
        lines.append("")
        lines.append(f"Hali ishlanmagan {len(check.hot_not_touched)} ta issiq mijoz:")
        for n in check.hot_not_touched[:_MAX_LIST]:
            lines.append(f"• {escape(n)}")
    if check.priority_now:
        lines.append("")
        lines.append("<b>Hozirgi prioritet:</b>")
        for i, ls in enumerate(check.priority_now, 1):
            lines.append(f"{i}. {escape(ls.name)} — <i>{escape(ls.action)}</i>")
    return "\n".join(lines)


def render_seller_evening(result: SellerEveningResult) -> str:
    s = result.seller
    lines = [
        "<b>Bugungi natija (18:30)</b>",
        "",
        f"Sales: {result.sales_done}/{s.expected_sales}",
        f"Revenue: {fmt_sum(result.revenue_today)} so'm",
        "",
    ]
    if result.solid_calls > 0 or result.total_calls > 0:
        mins = result.talk_seconds // 60
        target = result.solid_calls_target
        is_reached = result.solid_calls >= target
        status_icon = "✅" if is_reached else "⚠️"
        lines.append("📞 <b>Qo'ng'iroqlar tahlili (Moizvonki):</b>")
        lines.append(f"• Sifatli suhbatlar (≥3 daq): <b>{result.solid_calls}/{target} ta</b> {status_icon}")
        lines.append(f"• Jami qo'ng'iroqlar: {result.total_calls} ta ({result.answered_calls} ta ko'tarildi)")
        lines.append(f"• Gaplashilgan vaqt: {mins} daqiqa")
        if result.no_callback > 0:
            lines.append(f"• Qayta qilinmagan o'tkazib yuborilgan: <b>{result.no_callback} ta</b> ❌")
        lines.append("")
    lines.extend([
        f"Calls (CRM): {result.calls_done}/{s.calls}",
        f"Follow-ups: {result.follow_ups_done}/{s.follow_ups}",
        f"Meetings: {result.meetings_done}/{s.meetings}",
        f"Overdue: {result.overdue_count}",
    ])
    if result.tomorrow_closings:
        lines.append("")
        lines.append("Ertaga closingga yaqin:")
        for ls in result.tomorrow_closings:
            lines.append(f"• {escape(ls.name)}")
    return "\n".join(lines)


def render_ceo_morning(m: CeoMorning) -> str:
    lines = ["\U0001F7E2 <b>Sales Department — ertalabki holat</b>", ""]
    if m.weekly_recap is not None:
        lines.append("<b>O'tgan hafta yakuni:</b>")
        lines.append(_weekly_line(m.weekly_recap))
        lines.append("")
    lines.append(f"Sotuvchilar: {m.seller_count}")
    lines.append(f"Bugun kutilayotgan sotuv: {m.total_expected_sales}")
    lines.append(f"Kutilayotgan revenue: {fmt_sum(m.total_expected_revenue)} so'm")
    lines.append(f"Overdue: {m.total_overdue}")
    lines.append(f"<i>{DISCLAIMER}</i>")
    if m.no_owner:
        lines.append("")
        lines.append("⚠️ Mas'ulsiz bitimlar:")
        for n in _trim([escape(x) for x in m.no_owner]):
            lines.append(f"• {n}")
    if m.missing_tg:
        lines.append("")
        lines.append("Telegram ID yo'q: " + ", ".join(escape(x) for x in m.missing_tg))
    return "\n".join(lines)


def render_ceo_midday(m: CeoMidday) -> str:
    if not m.off_track:
        return "\U0001F7E2 Sales Department — hammasi rejada"
    lines = ["\U0001F7E1 <b>Sales Department — tushki nazorat</b>", ""]
    for name, why in m.off_track:
        lines.append(f"• {escape(name)} — {escape(why)}")
    return "\n".join(lines)


def render_ceo_dashboard(d: CeoDashboard) -> str:
    lines = [
        "<b>Sales Department</b>",
        "",
        f"Plan: {d.team_plan}",
        f"Fakt: {d.team_fakt}",
        f"Revenue: {fmt_sum(d.team_revenue)} so'm",
        f"Expected tomorrow: {fmt_sum(d.expected_tomorrow)} so'm",
        f"Overdue: {d.team_overdue}",
        "",
        _weekly_line(d.weekly),
        "",
        "<b>Sotuvchilar:</b>",
    ]
    for name, emoji, reasons in d.seller_lights:
        if reasons:
            lines.append(f"{emoji} {escape(name)} — {escape(reasons[0])}")
        else:
            lines.append(f"{emoji} {escape(name)}")
    if d.skipped_sellers:
        lines.append("")
        lines.append(f"<i>{d.skipped_sellers} sotuvchi o'tkazib yuborildi (xatolik).</i>")
    lines.append("")
    lines.append(f"<i>{DISCLAIMER}</i>")
    return "\n".join(lines)


def render_empty_roster_notice() -> str:
    return "ROP: hech qanday sotuvchi sozlanmagan."
