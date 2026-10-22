"""Hisobotni Excel (XLSX) va PDF ga eksport.

XLSX qo'shimcha kutubxonasiz (zip + SpreadsheetML) yoziladi — yangi dependency kiritilmaydi.
PDF — repo'dagi ``fpdf2`` (marketing/pdf_report.py bilan bir xil yondashuv).
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any, Sequence
from xml.sax.saxutils import escape

_FONT_DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("C:/Windows/Fonts"))
# Excel formula injection: =, +, -, @ bilan boshlangan matn formula bo'lib ishlamasin.
_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def _col(i: int) -> str:
    name = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        name = chr(65 + r) + name
    return name


def _cell(ref: str, value: Any, style: int = 0) -> str:
    s = f' s="{style}"' if style else ""
    if isinstance(value, bool) or value is None:
        value = "" if value is None else str(value)
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{s}><v>{value}</v></c>'
    text = str(value)
    if text.startswith(_FORMULA_PREFIX):
        text = "'" + text
    return f'<c r="{ref}" t="inlineStr"{s}><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def to_xlsx(headers: Sequence[str], rows: Sequence[Sequence[Any]], sheet: str = "Davomat") -> bytes:
    lines = ["<row r=\"1\">" + "".join(_cell(f"{_col(i)}1", h, 1) for i, h in enumerate(headers)) + "</row>"]
    for n, row in enumerate(rows, start=2):
        lines.append(f'<row r="{n}">' + "".join(_cell(f"{_col(i)}{n}", v) for i, v in enumerate(row)) + "</row>")
    sheet_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/>'
                 '</sheetView></sheetViews>'
                 f'<sheetData>{"".join(lines)}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>'),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>'),
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def to_pdf(title: str, subtitle: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(True, margin=12)
    family, unicode_ok = "helvetica", False
    for d in _FONT_DIRS:
        regular, bold = d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdf.add_font("Body", "", str(regular))
            pdf.add_font("Body", "B", str(bold))
            family, unicode_ok = "Body", True
            break

    def safe(v: Any) -> str:
        s = "" if v is None else str(v)
        return s if unicode_ok else s.encode("latin-1", "replace").decode("latin-1")

    pdf.add_page()
    pdf.set_font(family, "B", 15)
    pdf.cell(0, 9, safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 9)
    pdf.cell(0, 6, safe(subtitle), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    first = min(60.0, usable * 0.25)
    rest = (usable - first) / max(1, len(headers) - 1)
    widths = [first] + [rest] * (len(headers) - 1)
    pdf.set_font(family, "B", 8)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, safe(h), border=1, fill=True)
    pdf.ln()
    pdf.set_font(family, "", 8)
    if not rows:
        pdf.cell(0, 6, safe("Ma'lumot yo'q"), new_x="LMARGIN", new_y="NEXT")
    for row in rows:
        for i, (v, w) in enumerate(zip(row, widths)):
            text = safe(v)
            while len(text) > 4 and pdf.get_string_width(text) > w - 2:
                text = text[:-2]
            pdf.cell(w, 6, text, border=1, align="L" if i == 0 else "R")
        pdf.ln()
    return bytes(pdf.output())


SUMMARY_COLUMNS = [
    ("name", "Xodim"), ("scheduled_days", "Ish kuni"), ("present_days", "Kelgan"),
    ("on_time_days", "O'z vaqtida"), ("late_days", "Kechikkan kun"), ("late_minutes", "Kechikish, daq"),
    ("early_leave_days", "Erta ketgan"), ("early_leave_minutes", "Erta ketish, daq"),
    ("absent_days", "Kelmagan"), ("approved_leave_days", "Ruxsatli"), ("pending_review", "Tekshiruvda"),
    ("worked_hours", "Ishlangan soat"), ("overtime_hours", "Overtime soat"),
    ("missing_check_out", "Ketish belgisiz"),
]
EVENT_COLUMNS = [
    ("employee_name", "Xodim"), ("work_date", "Sana"), ("kind", "Turi"), ("local_time", "Vaqt"),
    ("status", "Holat"), ("minutes_late", "Kechikish, daq"), ("minutes_early", "Erta, daq"),
]


def table(rows: list[dict], columns: list[tuple[str, str]]) -> tuple[list[str], list[list[Any]]]:
    return [label for _, label in columns], [[r.get(key) for key, _ in columns] for r in rows]
