"""Oylik xulosa (Payroll manbasi) va Excel/PDF eksport."""
import io
import zipfile
from datetime import date, datetime, timedelta

from src.services.core.attendance import admin, export, summary
from test_attendance_flow import ALI, TZ5, _full, client, env, run  # noqa: F401  (fixture'lar)


def _live_from(db, day):
    db.conn.execute("UPDATE geofences SET created_at = ?", [f"{day} 00:00:00"])


def test_period_summary_counts_hours_lateness_and_absence(env):
    db, svc, clock, _ = env
    _live_from(db, "2026-10-01")
    # Payshanba: 10:30 keldi, 19:30 ketdi
    clock.t = datetime(2026, 10, 22, 10, 30, tzinfo=TZ5)
    _full(svc, db, clock, key="k-sum-0001")
    clock.t = datetime(2026, 10, 22, 19, 30, tzinfo=TZ5)
    _full(svc, db, clock, kind="check_out", key="k-sum-0002")
    # Juma ruxsatli kun
    run(admin.apply_correction(db, actor="owner", employee_id=1, work_date="2026-10-23",
                               new_status="APPROVED_LEAVE", reason="Kasallik varaqasi"))
    rows = run(summary.period_summary(db, date(2026, 10, 19), date(2026, 10, 25), today=date(2026, 10, 24)))
    ali = next(r for r in rows if r["employee_id"] == 1)
    assert ali["scheduled_days"] == 6  # Du–Sha
    assert ali["present_days"] == 1 and ali["late_days"] == 1 and ali["late_minutes"] == 30
    assert ali["worked_minutes"] == 540 and ali["overtime_minutes"] == 30
    assert ali["approved_leave_days"] == 1
    assert ali["absent_days"] == 4  # Du, Se, Ch, Sha; yakshanba — dam


def test_future_days_not_absent(env):
    db, _, _, _ = env
    _live_from(db, "2026-10-01")
    rows = run(summary.period_summary(db, date(2026, 10, 19), date(2026, 10, 31), today=date(2026, 10, 20)))
    assert all(r["absent_days"] == 2 for r in rows)  # faqat 19 va 20


def test_xlsx_is_valid_and_formula_safe():
    data = export.to_xlsx(["Xodim", "Soat"], [["=HYPERLINK(\"x\")", 8.5], ["Ali <b>", 7]])
    z = zipfile.ZipFile(io.BytesIO(data))
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "'=HYPERLINK" in sheet and "&lt;b&gt;" in sheet and "<v>8.5</v>" in sheet
    assert {"[Content_Types].xml", "xl/workbook.xml", "xl/styles.xml"} <= set(z.namelist())


def test_pdf_renders_uzbek_text():
    pdf = export.to_pdf("Davomat xulosasi", "2026-10-01 — 2026-10-31", ["Xodim", "Kelgan"], [["Mumtozmaxal O‘g‘li", 20]])
    assert pdf.startswith(b"%PDF") and len(pdf) > 500


def test_api_report_formats_and_rbac(client):
    c, state = client
    from src.api.rbac import Principal, Role
    q = "/api/attendance/admin/reports?start=2026-10-01&end=2026-10-31"
    assert c.get(q).status_code == 403  # oddiy xodim
    state["principal"] = Principal("owner", Role.OWNER, "session")
    assert c.get(q + "&view=summary").json()["view"] == "summary"
    x = c.get(q + "&view=summary&format=xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK" and "attachment" in x.headers["content-disposition"]
    p = c.get(q + "&format=pdf")
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
    assert c.get(q + "&format=exe").status_code == 422
    assert c.get("/api/attendance/admin/reports?start=2026-10-31&end=2026-10-01").status_code == 422
    emps = c.get("/api/attendance/admin/employees").json()["employees"]
    assert {e["name"] for e in emps} == {"Ali", "Vali"} and emps[0]["weekdays"] == [1, 2, 3, 4, 5, 6]


def test_days_before_go_live_not_counted(env):
    db, _, _, _ = env
    _live_from(db, "2026-10-21")
    rows = run(summary.period_summary(db, date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 22)))
    assert all(r["scheduled_days"] == 10 and r["absent_days"] == 2 for r in rows)  # 21–31: 10 ish kuni; 21, 22 kelmagan
