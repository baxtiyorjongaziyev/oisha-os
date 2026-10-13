"""Haftalik marketing hisoboti PDF ko'rinishida: kampaniyalar, kreativlar, sotuvchilar, rad etishlar.

Rahbarga yoki mijozga yuborish uchun — Telegram xabaridan farqli, saqlanadi va chop etiladi.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, List, Optional, Sequence

from fpdf import FPDF

from src.services.core.marketing import attribution_store, creative_report
from src.services.core.marketing.seller_metrics import aggregate as seller_aggregate
from src.services.core.marketing_attribution import MarketingAttributionService

_FONT_DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("C:/Windows/Fonts"))


def _money(v: Optional[float]) -> str:
    return "-" if v is None else f"{v:,.0f}".replace(",", " ")


class _Pdf(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="L", format="A4")
        self.set_auto_page_break(True, margin=12)
        self.unicode = False
        for d in _FONT_DIRS:
            regular, bold = d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf"
            if regular.exists() and bold.exists():
                self.add_font("Body", "", str(regular))
                self.add_font("Body", "B", str(bold))
                self.unicode = True
                break
        self.family_name = "Body" if self.unicode else "helvetica"

    def text_safe(self, s: Any) -> str:
        s = str(s)
        return s if self.unicode else s.encode("latin-1", "replace").decode("latin-1")

    def heading(self, text: str) -> None:
        self.ln(3)
        self.set_font(self.family_name, "B", 13)
        self.cell(0, 8, self.text_safe(text), new_x="LMARGIN", new_y="NEXT")

    def table(self, headers: Sequence[str], rows: List[Sequence[Any]], widths: Sequence[int]) -> None:
        if not rows:
            self.set_font(self.family_name, "", 9)
            self.cell(0, 6, self.text_safe("Ma'lumot yo'q"), new_x="LMARGIN", new_y="NEXT")
            return
        self.set_font(self.family_name, "B", 9)
        self.set_fill_color(235, 235, 235)
        for h, w in zip(headers, widths):
            self.cell(w, 7, self.text_safe(h), border=1, fill=True)
        self.ln()
        self.set_font(self.family_name, "", 9)
        for row in rows:
            for i, (v, w) in enumerate(zip(row, widths)):
                text = self.text_safe(v)
                while i == 0 and len(text) > 4 and self.get_string_width(text) > w - 2:
                    text = text[:-2]
                self.cell(w, 6, text, border=1, align="L" if i == 0 else "R")
            self.ln()


def build_pdf(start: str, end: str, out_path: Path) -> Path:
    pdf = _Pdf()
    pdf.add_page()
    pdf.set_font(pdf.family_name, "B", 16)
    pdf.cell(0, 10, pdf.text_safe(f"Marketing hisoboti: {start} - {end}"), new_x="LMARGIN", new_y="NEXT")

    report = MarketingAttributionService().get_performance_data(start, end)
    camp_rows = []
    for row in report["campaigns"]:
        camp_rows.append([
            row["campaign_name"], _money(row["spend"]), _money(row["leads"]),
            _money(row["cost_per_lead"]), _money(row["deals_won"]), _money(row["revenue_won"]),
            f"{row['roas']:.1f}x" if row["roas"] is not None else "-",
        ])
    pdf.set_font(pdf.family_name, "", 9)
    currency = report["totals"]["spend_currency"] or "noma'lum"
    revenue_currency = report["totals"]["revenue_currency"] or "noma'lum"
    pdf.cell(0, 6, pdf.text_safe(f"Xarajat: {currency}; daromad: {revenue_currency}; davr: lid yaratilgan sana"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.heading("Kampaniyalar")
    pdf.table(["Kampaniya", "Xarajat", "Lid", "CPL", "Sotuv", "Daromad", "ROAS"],
              camp_rows, [95, 30, 20, 30, 20, 40, 25])

    pdf.heading("Kreativlar")
    pdf.table(
        ["Reklama", "Xarajat", "Lid", "CPL", "Sifatli", "Sifatli narxi", "Sotuv", "ROAS"],
        [[r["ad_name"], _money(r["spend"]), r["leads"], _money(r["cpl"]), r["qualified"],
          _money(r["cpql"]), r["won"], f"{r['roas']:.1f}x" if r["roas"] is not None else "-"]
         for r in creative_report.build_rows(start, end)[:20]],
        [85, 30, 18, 28, 20, 32, 18, 25],
    )

    rows = attribution_store.seller_rows(start, end)
    names = {int(r["responsible_user_id"]): r["responsible_name"] for r in rows if r.get("responsible_name")}
    pdf.heading("Sotuvchilar (Meta lidlari)")
    pdf.table(
        ["Sotuvchi", "Lid", "Javob (median, daq)", "Javobsiz", "Sotuv", "Yopish %"],
        [[names.get(s["user_id"], f"#{s['user_id']}"), s["leads"],
          "-" if s["median_response_min"] is None else f"{s['median_response_min']:.0f}",
          s["untouched"], s["won"], "-" if s["close_rate"] is None else f"{s['close_rate']:.0f}%"]
         for s in seller_aggregate(rows)],
        [80, 20, 45, 30, 25, 30],
    )

    loss = attribution_store.loss_breakdown(start, end)
    pdf.heading(f"Rad etilgan lidlar: {loss['total']} ta")
    total = loss["total"] or 1
    pdf.table(["Toifa", "Soni", "Ulush"],
              [[k, v, f"{v * 100 / total:.0f}%"] for k, v in sorted(loss["by_category"].items())],
              [80, 25, 25])
    pdf.ln(2)
    pdf.table(["Sabab", "Soni"],
              [[k, v] for k, v in sorted(loss["by_reason"].items(), key=lambda kv: -kv[1])],
              [120, 25])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def weekly_pdf(today: dt.date, out_dir: Path) -> Path:
    start = (today - dt.timedelta(days=7)).isoformat()
    end = (today - dt.timedelta(days=1)).isoformat()
    return build_pdf(start, end, out_dir / f"marketing_{start}_{end}.pdf")
