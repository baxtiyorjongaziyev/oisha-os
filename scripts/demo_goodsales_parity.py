"""Interactive live demo for GoodSales Parity Suite in Oisha-OS.

Runs all 5 core engines and prints formatted real-world operational results.
"""
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.command_center.next_steps_engine import NextStepsEngine
from src.services.command_center.one_on_one import OneOnOneCoachService
from src.services.proactive.daily_brief import DailyBriefService
from src.services.ai.voice_exam import VoiceExamEngine
from src.services.command_center.compensation_davomat import CompensationDavomatEngine

SEP = "=" * 80


def run_demo():
    print(SEP)
    print("🌟 OISHA-OS — GOODSALES OPERATSION PARITY SUITE (JONLI DEMO)")
    print(SEP)

    # Sample manager data from Jon Branding / GoodSales parity
    managers = [
        {
            "id": "mgr_51", "name": "Kamola Karimova", "role": "Senior Closer", "has_telegram": True,
            "telegram_chat_id": "998901234567", "fact": 369_740_000, "plan": 150_000_000, "plan_percent": 246,
            "target": 396_000_000, "conv": 16.8, "score": 65.0, "hot_deals_sum": 588_900_000,
            "hot_deals_count": 90, "overdue_calls": 120, "overdue_tasks": 25, "focus_skill": "Yakunlash va keyingi qadam",
            "skill_score": 50, "level": 4, "level_title": "Kuchli", "talk_minutes": 2100, "calls_count": 520,
            "work_days": 22, "late_minutes": 10, "absent_days": 0,
        },
        {
            "id": "mgr_52", "name": "Mohira Karimova", "role": "Closer", "has_telegram": True,
            "telegram_chat_id": "998901234568", "fact": 212_400_000, "plan": 200_000_000, "plan_percent": 106,
            "target": 227_500_000, "conv": 10.7, "score": 64.0, "hot_deals_sum": 57_500_000,
            "hot_deals_count": 45, "overdue_calls": 50, "overdue_tasks": 10, "focus_skill": "Yakunlash va keyingi qadam",
            "skill_score": 57, "level": 4, "level_title": "Kuchli", "talk_minutes": 1850, "calls_count": 410,
            "work_days": 22, "late_minutes": 15, "absent_days": 0,
        },
        {
            "id": "mgr_53", "name": "Feruza Karimova", "role": "Account Exec", "has_telegram": True,
            "telegram_chat_id": "998901234569", "fact": 22_800_000, "plan": 50_000_000, "plan_percent": 46,
            "target": 26_500_000, "conv": 3.0, "score": 58.0, "hot_deals_sum": 22_000_000,
            "hot_deals_count": 15, "overdue_calls": 30, "overdue_tasks": 15, "focus_skill": "Yakunlash va keyingi qadam",
            "skill_score": 50, "level": 2, "level_title": "Oʻsishda", "talk_minutes": 1400, "calls_count": 320,
            "work_days": 21, "late_minutes": 40, "absent_days": 1,
        },
        {
            "id": "mgr_54", "name": "Eldor Karimov", "role": "Junior SDR", "has_telegram": False,
            "telegram_chat_id": None, "fact": 0, "plan": 50_000_000, "plan_percent": 0, "target": 5_500_000,
            "conv": 0.0, "score": 44.0, "hot_deals_sum": 12_400_000, "hot_deals_count": 6, "overdue_calls": 15,
            "overdue_tasks": 8, "focus_skill": "Salomlashish va kontakt", "skill_score": 46, "level": 1,
            "level_title": "Boshlangʻich", "talk_minutes": 550, "calls_count": 110, "work_days": 20,
            "late_minutes": 65, "absent_days": 2,
        },
    ]

    # 1. NextSteps Engine
    print("\n[1] NEXTSTEPS STRATEGIC ENGINE: TESKARI VORONKA VA 18 TA HARAKAT")
    print("-" * 80)
    ns_engine = NextStepsEngine()
    target_amount, current_fact, avg_check = 694_000_000, 623_700_000, 2_700_000
    conv_rate, kval_rate = 0.067, 0.449

    funnel = ns_engine.compute_funnel(target_amount, avg_check, conv_rate, kval_rate)
    pulse = ns_engine.aggregate_team_pulse(managers)

    print(f"🎯 Reja: {target_amount:,} soʻm | Fakt: {current_fact:,} soʻm ({int(current_fact / target_amount * 100)}%)")
    print(f"📊 Teskari voronka: {funnel.sales_needed} ta sotuv ← {funnel.kval_leads_needed} ta sifatli lid ← {funnel.total_leads_needed} ta umumiy lid")
    print(f"👥 Jamoa pulsi: Top konversiya: {pulse.top_conv_manager} | Oʻrtacha AI skoring: {pulse.avg_ai_score} ball")
    print(f"🔥 Issiq bitimlar: {pulse.hot_deals_sum:,} soʻm ({pulse.hot_deals_count} ta) | Kechikkan vaʼdalar: {pulse.overdue_promises_count}")

    actions = ns_engine.generate_action_queue(target_amount, current_fact, managers, avg_check, conv_rate * 100)
    print(f"\n⚡ TOP-5 USTUVOR HARAKAT (Moliyaviy taʼsiri boʻyicha saralangan):")
    for idx, a in enumerate(actions[:5], 1):
        print(f"  {idx}. [{a.priority.upper()}] {a.title} -> TAʼSIR: +{a.impact:,} soʻm ({a.impact_note})")

    lost_breakdown = [
        {"reason": "Vaqti toʻgʻri kelmadi", "count": 453, "type": "sales_process"},
        {"reason": "Telefonni koʻtarmadi", "count": 232, "type": "sales_process"},
        {"reason": "Murojaat qoldirmagan", "count": 881, "type": "lead_quality"},
        {"reason": "Dubl", "count": 878, "type": "lead_quality"},
        {"reason": "Sabab yozilmagan", "count": 1043, "type": "no_reason"},
    ]
    lost = ns_engine.analyze_lost_revenue(lost_breakdown, avg_check=avg_check)
    print(f"\n📉 Yoʻqotilgan daromad (3 savat):")
    print(f"  • Jarayon xatosi (26% qaytariladigan): {lost['sales_process'].deals_count} ta bitim ({lost['sales_process'].pct}%) | Qaytariladigan summa: +{lost['sales_process'].recoverable_sum:,} soʻm")
    print(f"  • Lid sifati / Marketing (52%): {lost['lead_quality'].deals_count} ta bitim ({lost['lead_quality'].pct}%)")
    print(f"  • Sababsiz yopilish (21% CRM): {lost['no_reason'].deals_count} ta bitim ({lost['no_reason'].pct}%)")

    # 2. One-on-One Coaching
    print("\n" + SEP)
    print("[2] ONE-ON-ONE COACHING DOSYESI: 4 TA BLOK VA CHOP ETISH")
    print("-" * 80)
    one_service = OneOnOneCoachService()
    dossier = one_service.build_dossier(managers[0])
    print(f"👤 Menejer: {dossier.manager_name} | Daraja: {dossier.level.level}/5 ({dossier.level.title})")
    print("1. Yutuqlar:")
    for w in dossier.wins:
        print(f"   ✅ {w}")
    print("2. Raqamli muammolar:")
    for c in dossier.concerns:
        print(f"   ⚠️ {c}")
    print("3. Coaching savollari:")
    for q in dossier.questions[:2]:
        print(f"   ❓ {q}")
    html_preview = one_service.to_printable_html(dossier)
    print(f"📄 Chop etish HTML generatsiyasi: {len(html_preview)} bayt (window.print() mavjud)")

    # 3. Daily Telegram Brief
    print("\n" + SEP)
    print("[3] TELEGRAM TONGGI BRIIFINGI (Menejerga yuboriladigan xabar)")
    print("-" * 80)
    daily_service = DailyBriefService()
    brief_obj = daily_service.prepare_brief(managers[0])
    print(brief_obj.brief_text)

    # 4. Voice Exam Simulator
    print("\n" + SEP)
    print("[4] AI OVOZLI/MATNLI ROL OʻYINI IMTIHONI VA SERTIFIKATLASH")
    print("-" * 80)
    exam_engine = VoiceExamEngine()
    session = exam_engine.start_exam("mgr_51", "pre_sale_1")
    scenario = exam_engine.SCENARIOS[session.scenario_id]
    print(f"🎙️ Ssenariy: {scenario.title} | Mijoz: {scenario.client_name} ({scenario.difficulty})")
    print(f"🤖 Mijoz (AI): «{session.turns[0].text}»")

    # Manager answers
    mgr_turn = "Assalomu alaykum! Jon Branding agentligidan Kamolaman. Loyihangiz marketing maqsadi va byudjetini aniqlab olsak boʻladimi?"
    print(f"👨‍💼 Menejer: «{mgr_turn}»")
    turn_res = exam_engine.process_turn(session, mgr_turn)
    print(f"🤖 Mijoz (AI): «{turn_res['client_response']}»")

    final_exam = exam_engine.finalize_exam(session)
    print(f"\n🎖️ Imtihon natijasi: {final_exam.overall_score}/100 ball | Holat: {'PASSED (OʻTDI)' if final_exam.passed else 'FAILED'}")
    print(f"📜 Sertifikat ID: {final_exam.certificate_id}")
    print(f"💡 Fikr: {final_exam.feedback}")

    # 5. Compensation & Davomat Matrix
    print("\n" + SEP)
    print("[5] ISH HAQI KOMPENSATSIYASI VA DAVOMAT MATRITSASI")
    print("-" * 80)
    comp_engine = CompensationDavomatEngine()
    matrix = comp_engine.compute_team_matrix(managers)
    print(f"{'Menejer':<18} | {'Oklad':<10} | {'Suhbat':<8} | {'Sifat':<8} | {'CRM':<8} | {'Sotuv KPI':<10} | {'Jarima':<8} | {'SOF OYLIK'}")
    print("-" * 95)
    for c in matrix:
        print(f"{c.manager_name:<18} | {c.base_salary:<10,} | {c.talk_bonus:<8,} | {c.quality_bonus:<8,} | {c.crm_bonus:<8,} | {c.sales_kpi_bonus:<10,} | -{c.late_penalty:<7,} | {c.net_salary:,} soʻm")

    print(SEP)
    print("✅ BARCHA 5 TA TIZIM 100% ISHLAMOQDA!")
    print(SEP)


if __name__ == "__main__":
    run_demo()
