import sys, os, subprocess

# Virtualenv auto-reexec guard
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_py = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
if os.path.exists(venv_py) and os.path.normpath(sys.executable).lower() != os.path.normpath(venv_py).lower():
    sys.exit(subprocess.call([venv_py] + sys.argv))

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, repo_root)
"""
Jon Branding Agency ERP & Enterprise Intelligence Parity Showcase
Run: python scripts/demo_agency_erp.py
"""

from datetime import datetime
from src.services.reporter.reconciliation import ReconciliationService
from src.services.customer_360.cooling_customers import (
    CoolingCustomerDetector,
    CustomerProfile,
)
from src.services.finance.project_margin import (
    ProjectMarginCalculator,
    ProjectCostInput,
)
from src.services.finance.investor_ledger import InvestorLedgerService
from src.services.reporter.pivot_builder import (
    AgencyPivotBuilder,
    AgencyRecord,
    PivotQuery,
)
from src.services.ai.mockup_generator import (
    BrandMockupEngine,
    MockupRequest,
)
from src.api.routes.agency_dashboard import AGENCY_WIDGETS, get_dashboard_summary


def print_header(title: str):
    print("\n" + "=" * 75)
    print(f"  >>> {title.upper()} <<<")
    print("=" * 75)


def demo_akt_sverka():
    print_header("1. B2B Akt Sverka (Solishtirma Dalolatnoma Generatori)")
    service = ReconciliationService()

    entries = [
        {
            "date": "2026-10-01",
            "document_number": "INV-2026/101",
            "document_type": "hisob-faktura",
            "description": "Artel yangi brending strategiyasi bosqichi",
            "debit": 80000000.0,
            "credit": 0.0,
        },
        {
            "date": "2026-10-05",
            "document_number": "BANK-4491",
            "document_type": "toʻlov",
            "description": "50% avans toʻlovi (bank oʻtkazmasi)",
            "debit": 0.0,
            "credit": 40000000.0,
        },
        {
            "date": "2026-10-20",
            "document_number": "INV-2026/108",
            "document_type": "hisob-faktura",
            "description": "Brendbook va qadoqlash konsepsiyasi",
            "debit": 50000000.0,
            "credit": 0.0,
        },
        {
            "date": "2026-10-28",
            "document_number": "BANK-4512",
            "document_type": "toʻlov",
            "description": "2-bosqich toʻlovi",
            "debit": 0.0,
            "credit": 50000000.0,
        },
    ]

    stmt = service.generate_statement(
        client_name="Artel Electronics MChJ",
        period_start="2026-10-01",
        period_end="2026-10-31",
        initial_balance=0.0,
        entries=entries,
    )

    print(stmt.to_text())
    print(f"\n[XULOSA] Yakuniy qoldiq: {stmt.closing_balance:,.2f} soʻm (Status: {stmt.status})")


def demo_cooling_customers():
    print_header("2. «Soviyotgan Mijozlar» & Churn Xavfi (Retention Engine)")
    detector = CoolingCustomerDetector(cooling_threshold_days=60, critical_churn_days=120)

    clients = [
        CustomerProfile(
            client_id="CL-01",
            client_name="Chust Pichoqlari",
            last_deal_date="2026-08-01",
            total_ltv=65000000.0,
            primary_service="Brending",
            manager="Farrux",
        ),
        CustomerProfile(
            client_id="CL-02",
            client_name="Safia Bakery",
            last_deal_date="2026-05-15",
            total_ltv=140000000.0,
            primary_service="Qadoq dizayni",
            manager="Madina",
        ),
        CustomerProfile(
            client_id="CL-03",
            client_name="Eko Qurilish",
            last_deal_date="2026-10-18",
            total_ltv=50000000.0,
            primary_service="Rebrending",
            manager="Farrux",
        ),
    ]

    ref_date = datetime(2026, 11, 1)
    cooling = detector.detect_cooling(clients, as_of_date=ref_date)

    print(f"Jami tekshirilgan mijozlar: {len(clients)} | Soviyotganlar: {len(cooling)}")
    for c in cooling:
        print(f"\n--- [{c.risk_level.upper()}] {c.profile.client_name} (Oxirgi bitimdan beri: {c.days_silent} kun) ---")
        mission = detector.generate_mission(c)
        print(f"Masʼul menejer: {mission.manager}")
        print(f"Tavsiya etilgan Upsell: {mission.recommended_upsell}")
        print("Surgical Mission qadamlari:")
        for step in mission.action_steps:
            print(f"   {step}")


def demo_unit_economics():
    print_header("3. Loyiha Tannarxi va Sof Marja (Unit Economics)")
    calc = ProjectMarginCalculator(default_hourly_rate=150000.0, default_tax_rate=0.04)

    projects = [
        ProjectCostInput(
            project_id="PRJ-A",
            project_name="Grand Savdo Premium Brending",
            client_name="Grand Savdo MChJ",
            contract_amount=70000000.0,
            direct_expenses=6000000.0,  # 3D render va video
            internal_hours=75.0,        # 75 soat x 150,000 = 11.25 mln
        ),
        ProjectCostInput(
            project_id="PRJ-B",
            project_name="Tezkor Qadoq va Cheksiz Pravkalar",
            client_name="Fast FMCG MChJ",
            contract_amount=20000000.0,
            direct_expenses=9000000.0,  # 9 mln tashqi xarajat
            internal_hours=110.0,       # 110 soat x 150,000 = 16.5 mln
        ),
    ]

    for p in projects:
        res = calc.calculate(p)
        print(f"\nLoyiha: {res.project_name} ({res.client_name})")
        print(f"   Shartnoma summasi:  {res.contract_amount:>12,.2f} soʻm")
        print(f"   Tashqi xarajatlar:  {res.direct_expenses:>12,.2f} soʻm")
        print(f"   Jamoa soatlik yuki: {res.internal_labor_cost:>12,.2f} soʻm")
        print(f"   Aylanma soliq (4%): {res.taxes_amount:>12,.2f} soʻm")
        print(f"   Jami tannarx:       {res.total_cost:>12,.2f} soʻm")
        print(f"   Sof foyda (Net):    {res.net_profit:>12,.2f} soʻm")
        print(f"   Sof marja foizi:    {res.net_margin_pct:>11.1f}% [{res.health_status.upper()}]")
        for ins in res.insights:
            print(f"   Tahlil xulosasi: {ins}")


def demo_investor_ledger():
    print_header("4. Investor & Hamkor Bitimlari (Dividend Ledger)")
    service = InvestorLedgerService()

    inv = service.register_investor(
        investor_id="INV-007",
        name="Sanjar Rahimov",
        initial_capital=200000000.0,
        default_profit_share_pct=30.0,
    )
    print(f"Investor roʻyxatga olindi: {inv.name} (Kapital: {inv.total_invested:,.2f} soʻm)")

    deal = service.allocate_deal(
        deal_id="DEAL-77",
        investor_id="INV-007",
        project_id="PRJ-AI-STARTUP",
        allocated_amount=50000000.0,
    )
    print(f"Loyiha bitimiga tikildi: {deal.allocated_amount:,.2f} soʻm (Ulush: {deal.profit_share_pct}%)")

    closed = service.close_deal("DEAL-77", project_net_profit=90000000.0)
    print(f"Loyiha yakunlandi. Jami sof foyda: 90,000,000 soʻm")
    print(f"Investor sof foydasi (30%): {closed.investor_profit:,.2f} soʻm")
    print(f"Investorga qaytariladigan jami summa: {closed.total_payout_due:,.2f} soʻm")


def demo_pivot_builder():
    print_header("5. Dinamik Pivot Konstruktor («Jadval Yigʻish»)")
    builder = AgencyPivotBuilder()

    records = [
        AgencyRecord("Artel", "Brending", "Farrux", "Alisher", "2026-10", 80000000.0, 25000000.0),
        AgencyRecord("Chust Pichoqlari", "Brending", "Madina", "Alisher", "2026-10", 45000000.0, 15000000.0),
        AgencyRecord("Safia Bakery", "Qadoq", "Madina", "Sardor", "2026-10", 55000000.0, 18000000.0),
        AgencyRecord("Akfa Medline", "Sayt", "Farrux", "Sardor", "2026-10", 35000000.0, 12000000.0),
    ]

    q = PivotQuery(row_dimension="service_type", sort_by="profit", sort_asc=False)
    res = builder.build(records, q)

    print(f"Guruhlash oʻlchami: {res.row_dimension.upper()} | Jami loyihalar: {res.total_count}")
    print(f"{'Kategoriya':<15} | {'Soni':<6} | {'Tushum':<14} | {'Xarajat':<14} | {'Sof Foyda':<14} | {'Marja %':<8}")
    print("-" * 80)
    for r in res.rows:
        print(f"{r.dimension_value:<15} | {r.count:<6} | {r.revenue:>14,.2f} | {r.cost:>14,.2f} | {r.profit:>14,.2f} | {r.margin_pct:>7.1f}%")
    print("-" * 80)
    print(f"{'JAMI':<15} | {res.total_count:<6} | {res.total_revenue:>14,.2f} | {res.total_cost:>14,.2f} | {res.total_profit:>14,.2f} | {res.average_margin_pct:>7.1f}%")


def demo_ai_mockups():
    print_header("6. AI Brand Mockup Prompt Engine (Particum Dressing Analogi)")
    engine = BrandMockupEngine()

    req = MockupRequest(
        brand_name="Chust Pichoqlari",
        industry="Milliy hunarmandchilik va pichoqchilik",
        primary_colors=["Toʻq qora #111111", "Poʻlat metall #E0E0E0", "Oltin naqsh #D4AF37"],
        mockup_type="billboard_tashkent",
        environment="outdoor_city",
    )

    p = engine.generate_prompt(req)
    print(f"Format: {p.aspect_ratio} | Turi: {p.mockup_type}")
    print(f"Oʻzbekcha tavsif: {p.prompt_uz}")
    print(f"\nImagen 3 / Midjourney Prompt:\n{p.prompt}")
    print(f"\nNegative Prompt:\n{p.negative_prompt}")


def demo_agency_dashboard_api():
    print_header("7. 20-Vidjetli Agentlik Boshqaruv Paneli (Dashboard API)")
    print(f"Jami integratsiyalangan vidjetlar: {len(AGENCY_WIDGETS)} ta")
    summary = get_dashboard_summary(period="month")

    cats = summary["categories"]
    print("\n[MOLIYA]")
    print(f"   Jami tushum:  {cats['moliya']['total_revenue']:,.2f} soʻm")
    print(f"   Yalpi foyda:  {cats['moliya']['gross_profit']:,.2f} soʻm")
    print(f"   Kassa/Bank:   {cats['moliya']['bank_balance']:,.2f} soʻm")
    print("\n[SAVDO]")
    print(f"   Aktiv bitimlar: {cats['savdo']['pipeline_deals']} ta")
    print(f"   Konversiya:     {cats['savdo']['conversion_rate']}%")
    print(f"   Oʻrtacha chek:  {cats['savdo']['avg_contract_value']:,.2f} soʻm")
    print("\n[QARZ]")
    print(f"   Debitorlik (Bizga qarz): {cats['qarz']['receivables']:,.2f} soʻm")
    print(f"   Muddati oʻtgan qarz:     {cats['qarz']['overdue_debts']:,.2f} soʻm")
    print("\n[LOYIHALAR & JAMOA]")
    print(f"   Aktiv loyihalar: {cats['loyihalar']['active_projects']} ta | Deadline xavfi: {cats['loyihalar']['deadline_risks']} ta")
    print(f"   Jamoa davomati:  {cats['jamoa']['team_attendance']} | Bandlik: {cats['jamoa']['team_utilization']}%")


if __name__ == "__main__":
    print("\n" + "#" * 75)
    print("  JON BRANDING AGENCY ERP & PARITY LIVE SHOWCASE")
    print("#" * 75)
    demo_akt_sverka()
    demo_cooling_customers()
    demo_unit_economics()
    demo_investor_ledger()
    demo_pivot_builder()
    demo_ai_mockups()
    demo_agency_dashboard_api()
    print("\n" + "#" * 75)
    print("  BARCHA 7 TA MODUL MUVAFFAQIYATLI ISHLADI!")
    print("#" * 75 + "\n")
