"""Qo'ng'iroqlar hisobotini Telegram uchun formatlash va ROP tahlili (Moizvonki).

Ushbu modul:
- Emojilari kamaytirilgan, toza va professional ko'rinish beradi.
- Har kunlik raqamlarga asoslangan ROP (sotuv bo'limi boshlig'i) tahlilini kiritadi.
- 50+ qo'ng'iroq qilganlarni maqtaydi, 50 tadan kam qilganlarga aniq motivatsiya va maqsad beradi.
- O'tkazib yuborilgan qayta qo'ng'iroqlarni va soatbay taqsimotni tahlil qiladi.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

TASHKENT = timezone(timedelta(hours=5))
TARGET_SOLID_CALLS = 50  # 50 ta ko'targan va kamida 3 minut gaplashilgan mijoz


def fmt_duration(seconds: int) -> str:
    """Soniyalarni ixcham va tushunarli formatga keltiradi."""
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} soat {m} daq"
    if m:
        return f"{m} daq {s} son"
    return f"{s} son"


def _hhmm(ts: int) -> str:
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%H:%M") if ts else "—"


def _rep_stats_lines(r: any) -> List[str]:
    """Sotuvchi bo'yicha toza, emojilari kamaytirilgan statistika qatorlari."""
    solid = getattr(r, "solid_calls", 0)
    lines = [
        f"   • Jami: <b>{r.total}</b> | Javob: <b>{r.answered}</b> | Ko'tarmadi: <b>{r.missed}</b> ({r.answer_rate}%)",
        f"   • Sifatli suhbat (≥3 daq): <b>{solid} ta</b>",
        f"   • Chiquvchi: {r.outgoing} (javob: {r.outgoing_answered} / olinmadi: {r.outgoing_missed})",
        f"   • Kiruvchi: {r.incoming} (javob: {r.incoming_answered} / javobsiz: {r.incoming_missed})",
        f"   • Suhbat vaqti: <b>{fmt_duration(r.talk_seconds)}</b>",
    ]
    if r.answered:
        lines.append(f"   • O'rtacha suhbat: {fmt_duration(r.avg_talk)} | Eng uzun: {fmt_duration(r.longest)}")

    meta = [f"Mijozlar: {len(r.clients)}"]
    if getattr(r, "short_calls", 0):
        meta.append(f"&lt;10s: {r.short_calls}")
    if r.incoming_answered:
        meta.append(f"Kutish: {fmt_duration(r.avg_wait)}")
    lines.append(f"   • {' | '.join(meta)}")
    lines.append(f"   • Ish vaqti: {_hhmm(r.first_ts)} – {_hhmm(r.last_ts)}")

    if getattr(r, "no_callback", 0):
        lines.append(f"   • <b>Qayta qo'ng'iroq qarzi: {r.no_callback} ta</b>")
    return lines


def _team_stats_lines(t: any, team_label: str) -> List[str]:
    """Jamoa bo'yicha umumiy ko'rsatkichlar."""
    solid = getattr(t, "solid_calls", 0)
    lines = [
        "────────────────────────────",
        f"<b>Jamoa bo'yicha ({team_label})</b>",
        f"• Jami qo'ng'iroqlar: <b>{t.total}</b> (javob: <b>{t.answered}</b> / <b>{t.answer_rate}%</b>)",
        f"• Sifatli suhbatlar (≥3 daq): <b>{solid} ta</b>",
        f"• Chiquvchi: {t.outgoing} | Kiruvchi: {t.incoming}",
        f"• Umumiy suhbat vaqti: <b>{fmt_duration(t.talk_seconds)}</b>",
    ]
    if t.answered:
        lines.append(f"• O'rtacha suhbat: {fmt_duration(t.avg_talk)} | Eng uzun: {fmt_duration(t.longest)}")
    lines.append(f"• Qamrab olingan mijozlar: {len(t.clients)}")
    lines.append(f"• Jamoa ish diapazoni: {_hhmm(t.first_ts)} – {_hhmm(t.last_ts)}")
    if getattr(t, "no_callback", 0):
        lines.append(f"• <b>Jami qayta qo'ng'iroq qarzi: {t.no_callback} ta</b>")
    return lines


def _build_rop_feedback(active_reps: List[any], names: Dict[str, str], hourly: Dict[int, int]) -> List[str]:
    """ROP odamga o'xshash professional, faktlarga asoslangan motivatsiya bloki."""
    e = html.escape
    feedback = [
        "────────────────────────────",
        "<b>ROP Xulosasi va Ko'rsatmasi</b>",
        f"<i>Kunlik standartimiz: kamida <b>{TARGET_SOLID_CALLS} ta ko'targan va 3+ daqiqa</b> to'liq gaplashilgan sifatli mijoz.</i>",
        "",
    ]

    for r in active_reps:
        rep_name = _get_display_name(r.account, names)
        solid = getattr(r, "solid_calls", 0)
        needed = TARGET_SOLID_CALLS - solid
        talk_str = fmt_duration(r.talk_seconds)

        if solid >= TARGET_SOLID_CALLS:
            text = (
                f"<b>{e(rep_name)}</b> ({solid} ta 3+ daqiqalik suhbat): "
                f"Barakalla! Kunlik {TARGET_SOLID_CALLS} ta sifatli suhbat marrasini a'lo darajada bajardingiz! "
                f"Jami {r.answered} ta javob olingan mijozdan {solid} tasida chuqur 3+ daqiqa gaplashilgan. "
                f"Umumiy {talk_str} efir vaqti — bu haqiqiy natijador sotuvchining ishi! Shu sifatni ushlang."
            )
        elif solid >= 25:
            text = (
                f"<b>{e(rep_name)}</b> ({solid} ta 3+ daqiqalik suhbat): "
                f"Yaxshi qadam, lekin marraga yetish uchun yana {needed} ta to'liq suhbat yetishmadi. "
                f"Jami {r.answered} ta mijoz ko'targan, biroq suhbatlarni tez tugatmasdan, mijoz ehtiyojini "
                f"chuqurroq aniqlab 3 daqiqadan oshirish kerak. Bugun 50 ta to'liq suhbatni nishonga oling!"
            )
        elif solid >= 10:
            text = (
                f"<b>{e(rep_name)}</b> ({solid} ta 3+ daqiqalik suhbat): "
                f"Harakat bor, lekin asosiy maqsad — ko'targan mijoz bilan kamida 3 daqiqa sifatli muloqot qilish. "
                f"Sizda {r.answered} ta javobdan atigi {solid} tasi 3 daqiqadan oshgan. Skriptni mustahkamlab, "
                f"mijozni ko'proq savol bilan ushlab turing va {TARGET_SOLID_CALLS} taga yetkazing!"
            )
        else:
            text = (
                f"<b>{e(rep_name)}</b> ({solid} ta 3+ daqiqalik suhbat): "
                f"Bu natija yetarli emas! Kun bo'yi atigi {solid} ta mijoz bilan 3+ daqiqa gaplashilgan. "
                f"Shunchaki go'shak ko'tarilishi kifoya qilmaydi, har bir mijoz bilan to'liq ehtiyojni aniqlab, "
                f"taqdimot qilish kerak. Bugun go'shakni dadil oling va 50 ta sifatli suhbatni bajaring!"
            )

        if getattr(r, "no_callback", 0):
            text += f" <i>(Eslatma: {r.no_callback} ta qayta qo'ng'iroq qarzingiz bor, birinchi navbatda yoping!)</i>"
        feedback.append(f"• {text}")
        feedback.append("")

    return feedback


def _build_action_items(missed_calls: List[dict], hourly: Dict[int, int], names: Dict[str, str]) -> List[str]:
    """Bugungi 1-darajali vazifalar."""
    items = [
        "<b>Bugungi asosiy vazifalar:</b>",
        f"1. <b>Sifatli marra:</b> Har bir sotuvchida <b>kamida 50 ta ko'targan va 3+ daqiqa gaplashilgan</b> mijoz.",
    ]

    if hourly:
        peak_hour = max(hourly, key=hourly.get)
        items.append(
            f"2. <b>Vaqt taqsimoti:</b> Qo'ng'iroqlarni kun bo'yi teng taqsimlash "
            f"(barcha terishlarni {peak_hour:02d}:00 ga yig'ib qo'ymasdan, ertalabdan start olish)."
        )
    else:
        items.append("2. <b>Vaqt taqsimoti:</b> Ertalab 10:00 dan boshlab faol raqam terish.")

    if missed_calls:
        items.append(
            f"3. <b>Qarzlarni yopish:</b> Qayta qo'ng'iroq qilinmagan {len(missed_calls)} ta "
            f"mijozga zudlik bilan birinchi navbatda bog'lanish!"
        )
    else:
        items.append("3. <b>Mijozlar bilan sifat:</b> Har bir suhbatni keyingi aniq qadam bilan yakunlash.")

    return items


def _get_display_name(account: str, names: Dict[str, str]) -> str:
    if account.lower() in names:
        return names[account.lower()]
    local = account.split("@")[0]
    return local.capitalize() if local else account


def format_report_rop(report: any, names: Optional[Dict[str, str]] = None) -> str:
    """Hisobotni emojilari kamaytirilgan, tartibli va ROP motivatsiyasi bilan formatlaydi."""
    names = names or {}
    e = html.escape
    lines = [f"📞 <b>Qo'ng'iroqlar hisoboti — {e(report.day)}</b>", ""]

    active = [r for r in report.reps if r.total]
    if not active:
        lines.append("Bu kunda qo'ng'iroq bo'lmagan.")
        return "\n".join(lines)

    # 1. Har bir sotuvchi ko'rsatkichlari
    for i, r in enumerate(report.reps, 1):
        name = e(_get_display_name(r.account, names))
        solid = getattr(r, "solid_calls", 0)
        badge = " [50+ SIFATLI MARRA]" if solid >= TARGET_SOLID_CALLS else ""
        lines.append(f"<b>{i}. {name}</b>{badge}")
        lines += _rep_stats_lines(r) if r.total else ["   🚫 Qo'ng'iroq yo'q"]
        lines.append("")

    # 2. Jamoa bo'yicha umumiy statistika
    idle = len(report.reps) - len(active)
    team_label = f"{len(active)} sotuvchi" + (f", {idle} tasi qo'ng'iroqsiz" if idle else "")
    lines += _team_stats_lines(report.total, team_label)

    # 3. Soatbay taqsimot
    if report.hourly:
        peak = max(report.hourly, key=report.hourly.get)
        lines.append(f"• Eng faol soat: {peak:02d}:00 ({report.hourly[peak]} ta)")
        hours = " ".join(f"{h:02d}h:{report.hourly[h]}" for h in sorted(report.hourly))
        lines.append(f"• Soatlar: {hours}")

    # 4. Qayta qo'ng'iroq qilinmagan mijozlar
    if report.missed_no_callback:
        lines += ["", f"⚠️ <b>Qayta qo'ng'iroq qilinmagan mijozlar: {len(report.missed_no_callback)} ta</b>"]
        for c in report.missed_no_callback[:20]:
            number = c.get("client_number") or ""
            who = c.get("client_name") or number or "?"
            if c.get("client_name") and number:
                who = f"{who} ({number})"
            rep = _get_display_name(c.get("user_account") or "", names)
            lines.append(f"   • {_hhmm(c.get('start_time') or 0)} {e(str(who))} → {e(rep)}")
        if len(report.missed_no_callback) > 20:
            lines.append(f"   … yana {len(report.missed_no_callback) - 20} ta")

    # 5. ROP Xulosasi va Motivatsiya
    lines += [""]
    lines += _build_rop_feedback(active, names, report.hourly)

    # 6. Bugungi asosiy vazifalar
    lines += _build_action_items(report.missed_no_callback, report.hourly, names)

    return "\n".join(lines)
