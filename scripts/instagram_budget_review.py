#!/usr/bin/env python
"""
Instagram Lead Ads byudjetini har chorakda ko'rib chiqish va manba balansini tahlil qilish skripti.

Vazifalari:
1. data/leadgen_delivery.db dan UTC Outsource va Inhouse (Jon Branding) o'rtasidagi lidlar
   taqsimotini hisoblaydi va 50/50 balansi saqlanganligini tekshiradi.
2. data/meta_ad_spend.db va konfiguratsiyadan choraklik reklama xarajatlarini,
   olingan lidlar sonini hamda bitta lid narxini (CPL) hisoblaydi.
3. Keyingi chorak uchun tavsiyalar va manbani qayta muvozanatlash bo'yicha ko'rsatma beradi.
4. Telegram va Discord kanallariga tahliliy hisobot kartochkasini yuboradi.

Ishga tushirish:
    python -m scripts.instagram_budget_review [--notify]
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BudgetReview")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_QUARTERLY_BUDGET_USD = 1500.0


def _get_quarter_date_range(year: int, quarter: int) -> Tuple[datetime.date, datetime.date]:
    """Berilgan yil va chorak uchun boshlanish va tugash sanasini qaytaradi."""
    start_month = 3 * quarter - 2
    end_month = 3 * quarter
    start_date = datetime.date(year, start_month, 1)
    if end_month in (1, 3, 5, 7, 8, 10, 12):
        end_day = 31
    elif end_month in (4, 6, 9, 11):
        end_day = 30
    else:
        end_day = 29 if year % 4 == 0 else 28
    end_date = datetime.date(year, end_month, end_day)
    return start_date, end_date


def get_source_balance(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    UTC Outsource vs Inhouse manbalar bo'yicha lidlar balansini hisoblaydi.
    """
    db_path = DATA_DIR / "leadgen_delivery.db"
    if not db_path.exists():
        return {"total": 0, "utc": 0, "inhouse": 0, "unassigned": 0, "utc_pct": 0.0, "inhouse_pct": 0.0}

    with sqlite3.connect(db_path, timeout=10) as conn:
        cursor = conn.cursor()
        if start_date and end_date:
            cursor.execute(
                """
                SELECT destination, COUNT(*)
                FROM deliveries
                WHERE updated_at >= ? AND updated_at <= ?
                GROUP BY destination
                """,
                (start_date, end_date),
            )
        else:
            cursor.execute("SELECT destination, COUNT(*) FROM deliveries GROUP BY destination")
        rows = cursor.fetchall()

    counts = {dest: cnt for dest, cnt in rows}
    utc_count = counts.get("utc", 0)
    inhouse_count = counts.get("inhouse", 0)
    unassigned = sum(cnt for dest, cnt in counts.items() if dest not in ("utc", "inhouse"))
    total = sum(counts.values())

    utc_pct = round((utc_count / total * 100), 1) if total > 0 else 0.0
    inhouse_pct = round((inhouse_count / total * 100), 1) if total > 0 else 0.0

    return {
        "total": total,
        "utc": utc_count,
        "inhouse": inhouse_count,
        "unassigned": unassigned,
        "utc_pct": utc_pct,
        "inhouse_pct": inhouse_pct,
    }


def get_meta_ad_spend(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    meta_ad_spend.db bazasidan berilgan oraliqdagi reklama xarajatlarini oladi.
    """
    db_path = DATA_DIR / "meta_ad_spend.db"
    total_spend = 0.0
    total_impressions = 0
    total_clicks = 0
    meta_leads = 0

    if db_path.exists():
        with sqlite3.connect(db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT SUM(spend), SUM(impressions), SUM(clicks), SUM(meta_leads)
                FROM meta_ad_spend
                WHERE date >= ? AND date <= ?
                """,
                (start_date, end_date),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                total_spend = float(row[0] or 0.0)
                total_impressions = int(row[1] or 0)
                total_clicks = int(row[2] or 0)
                meta_leads = int(row[3] or 0)

    # Agar lokal xarajatlar bo'sh bo'lsa, env dagi byudjet ko'rsatkichlaridan foydalaniladi
    monthly_budget_str = os.getenv("IG_LEADGEN_MONTHLY_BUDGET") or os.getenv("IG_LEADGEN_QUARTERLY_BUDGET")
    target_budget = float(monthly_budget_str) if monthly_budget_str else DEFAULT_QUARTERLY_BUDGET_USD

    return {
        "spend": round(total_spend, 2),
        "target_budget": target_budget,
        "impressions": total_impressions,
        "clicks": total_clicks,
        "meta_leads": meta_leads,
    }


def evaluate_balance_and_budget(source_stats: Dict[str, Any], spend_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manba balansi va byudjet bo'yicha tahlil hamda tavsiyalar shakllantiradi.
    """
    utc_pct = source_stats["utc_pct"]
    inhouse_pct = source_stats["inhouse_pct"]
    total_leads = source_stats["total"]
    spend = spend_stats["spend"]
    target_budget = spend_stats["target_budget"]

    cpl = round(spend / total_leads, 2) if total_leads > 0 and spend > 0 else 0.0
    budget_usage_pct = round((spend / target_budget * 100), 1) if target_budget > 0 else 0.0

    # 1. Manba balansi holati (Ideal: 50% UTC / 50% Inhouse)
    diff = abs(utc_pct - inhouse_pct)
    if diff <= 10.0:
        balance_status = "BARQAROR (50/50 muvozanatda)"
        balance_advice = "Taqsimot algoritmi to'g'ri ishlamoqda. Mavjud rotatsiyani davom ettirish tavsiya etiladi."
    elif utc_pct < inhouse_pct:
        balance_status = f"OG'ISH: Inhouse ustun ({inhouse_pct}% vs {utc_pct}%)"
        balance_advice = "UTC Outsource kanalida lidlar kamroq. Keyingi chorakda UTC ga oqimni kuchaytirish zarur."
    else:
        balance_status = f"OG'ISH: UTC Outsource ustun ({utc_pct}% vs {inhouse_pct}%)"
        balance_advice = "Inhouse sotuv bo'limi uchun lidlar kamaygan. Inhouse taqsimotini oshirish tavsiya etiladi."

    # 2. Byudjet holati
    if spend == 0.0:
        budget_status = "Statik tahlil (Haqiqiy Meta spend sinxronizatsiyasi kutilyapti)"
        budget_advice = f"Choraklik reja: ${target_budget:,.0f}. Kampaniyalar faoliyatini kuzatib boring."
    elif budget_usage_pct > 110.0:
        budget_status = f"ORTIQCHA SARF ({budget_usage_pct}%)"
        budget_advice = "Byudjet limitdan oshgan. Reklama stavkalarini optimallashtirish va auditoriyani toraytirish lozim."
    elif budget_usage_pct < 80.0:
        budget_status = f"KAM SARF ({budget_usage_pct}%)"
        budget_advice = "Byudjet to'liq o'zlashtirilmagan. Qo'shimcha lidlar oqimi uchun sarfni oshirish imkoni mavjud."
    else:
        budget_status = f"ME'YORDA ({budget_usage_pct}%)"
        budget_advice = "Byudjet sarfi reja doirasida samarali amalga oshirilmoqda."

    return {
        "cpl": cpl,
        "budget_usage_pct": budget_usage_pct,
        "balance_status": balance_status,
        "balance_advice": balance_advice,
        "budget_status": budget_status,
        "budget_advice": budget_advice,
    }


def send_quarterly_report(
    year: int,
    quarter: int,
    source_stats: Dict[str, Any],
    spend_stats: Dict[str, Any],
    eval_results: Dict[str, Any],
) -> bool:
    """Telegram va Discord orqali choraklik hisobot kartochkasini yuboradi."""
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    chat_id = os.getenv("TARGET_LEADS_GROUP_ID") or "-1003854308552"
    topic_id = os.getenv("TARGET_LEADS_TOPIC_ID") or "1020"

    lines = [
        f"📊 <b>[OISHA: INSTAGRAM LEADGEN CHORAKLIK TAHLIL (Q{quarter} {year})]</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>Jami qayd etilgan lidlar:</b> <b>{source_stats['total']} ta</b>",
        "",
        "🏢 <b>Manba balansi (50/50 Split):</b>",
        f"• 🌐 <b>UTC Outsource:</b> {source_stats['utc']} ta (<b>{source_stats['utc_pct']}%</b>)",
        f"• 🏠 <b>Inhouse (Jon Branding):</b> {source_stats['inhouse']} ta (<b>{source_stats['inhouse_pct']}%</b>)",
        f"• ⚖️ <b>Balans holati:</b> <i>{eval_results['balance_status']}</i>",
        "",
        "💰 <b>Byudjet va Sarf:</b>",
        f"• 💵 <b>Choraklik reja:</b> ${spend_stats['target_budget']:,.2f}",
        f"• 💳 <b>Amaldagi sarf:</b> ${spend_stats['spend']:,.2f}",
        f"• 📉 <b>Cost Per Lead (CPL):</b> ${eval_results['cpl']:.2f}",
        f"• 📌 <b>Byudjet holati:</b> <i>{eval_results['budget_status']}</i>",
        "",
        "💡 <b>Strategik tavsiyalar:</b>",
        f"1. <b>Balans:</b> {eval_results['balance_advice']}",
        f"2. <b>Byudjet:</b> {eval_results['budget_advice']}",
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ <i>Choraklik reja avtomatik qayta ko'rib chiqildi.</i>",
    ]
    report_text = "\n".join(lines)

    # 1. Telegram
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": report_text,
            "parse_mode": "HTML",
        }
        if topic_id:
            try:
                payload["message_thread_id"] = int(topic_id)
            except ValueError:
                pass
        try:
            requests.post(url, json=payload, timeout=15)
            logger.info("[TG] Choraklik hisobot Telegramga yuborildi.")
        except Exception as exc:
            logger.error(f"[TG] Xabar yuborishda xato: {exc}")

    # 2. Discord
    discord_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if discord_url:
        discord_text = report_text.replace("<b>", "**").replace("</b>", "**").replace("<i>", "*").replace("</i>", "*")
        try:
            requests.post(discord_url, json={"content": discord_text}, timeout=15)
            logger.info("[Discord] Choraklik hisobot Discordga yuborildi.")
        except Exception as exc:
            logger.error(f"[Discord] Webhook xatosi: {exc}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Leadgen Choraklik Byudjet va Manba Tahlili")
    parser.add_argument("--year", type=int, default=None, help="Tahlil qilinayotgan yil")
    parser.add_argument("--quarter", type=int, default=None, help="Tahlil qilinayotgan chorak (1-4)")
    parser.add_argument("--notify", action="store_true", help="Natijalarni Telegram/Discord ga yuborish")
    args = parser.parse_args()

    today = datetime.date.today()
    current_year = args.year or today.year
    current_quarter = args.quarter or ((today.month - 1) // 3 + 1)

    start_date, end_date = _get_quarter_date_range(current_year, current_quarter)
    logger.info(f"Q{current_quarter} {current_year} ({start_date} - {end_date}) tahlili boshlandi...")

    source_stats = get_source_balance(start_date.isoformat(), end_date.isoformat())
    spend_stats = get_meta_ad_spend(start_date.isoformat(), end_date.isoformat())
    eval_results = evaluate_balance_and_budget(source_stats, spend_stats)

    logger.info(f"Lidlar: Jami {source_stats['total']} (UTC: {source_stats['utc']}, Inhouse: {source_stats['inhouse']})")
    logger.info(f"Balans: {eval_results['balance_status']}")
    logger.info(f"Byudjet: {eval_results['budget_status']}")

    if args.notify:
        send_quarterly_report(current_year, current_quarter, source_stats, spend_stats, eval_results)


if __name__ == "__main__":
    main()
