"""Airtable (Finance V2) → Telegram moliya hisobotlari.

Beshta rejali hisobot/eslatma:

* **Qarzdorlik**       — har dushanba 09:00, to'lovi tugallanmagan loyihalar
* **P&L**              — har oyning 1-sanasi 09:00, o'tgan oyning foyda/zarar hisoboti
* **Balans**           — har kuni 09:00, hisoblardagi joriy qoldiq
* **Cashflow**         — har kuni 19:00, shu oyning kirim/chiqim/sof oqimi
* **Balans eslatmasi** — har kuni 20:00, moliyachiga kunlik balans kiritishni eslatadi

Har biri o'z topikiga tushadi. Topic ID'lar ``settings.py`` da allaqachon
e'lon qilingan (``HISOBCHI_QARZDORLIK_TOPIC_ID``, ``HISOBCHI_PNL_TOPIC_ID``,
``HISOBCHI_CASHFLOW_TOPIC_ID``, ``HISOBCHI_BALANCE_TOPIC_ID``) va deploy
``.env`` ga yoziladi.

Manba — Airtable ``Tranzaksiyalar``, ``Loyihalar``, ``Hisoblar``, ``Oylik P&L``
jadvallari. Eski Kirim/Chiqim jadvallari ishlatilmaydi.
"""

from src.schedulers.moliya.balans import (
    build_balans_report,
    run_balans_eslatmasi,
    run_balans_report,
)
from src.schedulers.moliya.cashflow import build_cashflow_report, run_cashflow_report
from src.schedulers.moliya.loop import moliya_hisobotlari_loop
from src.schedulers.moliya.pnl import build_pnl_report, run_pnl_report
from src.schedulers.moliya.qarzdorlik import build_qarzdorlik_report, run_qarzdorlik_report

__all__ = [
    "build_balans_report",
    "run_balans_eslatmasi",
    "run_balans_report",
    "build_cashflow_report",
    "run_cashflow_report",
    "moliya_hisobotlari_loop",
    "build_pnl_report",
    "run_pnl_report",
    "build_qarzdorlik_report",
    "run_qarzdorlik_report",
]
