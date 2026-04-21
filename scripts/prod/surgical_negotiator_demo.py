"""
Surgical Negotiator Demo
Oisha-OS Autonomous Negotiations Demo Script
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.agents import (
    get_surgical_negotiator,
    negotiate,
    DealStage,
    DealPriority,
)
from src.agents.surgical_negotiator import SurgicalNegotiator


async def demo_new_lead():
    """Yangi lead bilan demo suhbat"""
    
    print("=" * 60)
    print("🤖 OISHA-OS SURGICAL NEGOTIATOR DEMO")
    print("=" * 60)
    print()
    
    negotiator = get_surgical_negotiator()
    user_id = "demo_user_001"
    
    # Conversation simulation
    conversation = [
        {
            "user": "Salom, web sayt uchun narx necha pul?",
            "info": {"first_name": "Aziz", "last_name": "Karimov", "source": "telegram"}
        },
        {
            "user": "Korporativ sayt kerak, mahsulotlarimizni sotadigan",
            "info": None
        },
        {
            "user": "Narx qimmatroq ekan. Boshqa agentlik 3000$ da qilyapti",
            "info": None
        },
        {
            "user": "To'g'ri, sizlar portfolio yaxshi. 5000$ bo'lsa ishlaymiz",
            "info": None
        },
        {
            "user": "TAYYOR. Shartnoma yuboring",
            "info": None
        }
    ]
    
    print("📋 Simulyatsiya: E-commerce web sayt loyihasi")
    print("Mijoz: Aziz Karimov")
    print("Budjet: $3000-5000")
    print("-" * 60)
    print()
    
    for i, msg in enumerate(conversation, 1):
        print(f"\n{'─' * 60}")
        print(f"💬 XABAR {i}")
        print(f"{'─' * 60}")
        print(f"👤 Mijoz: {msg['user']}")
        print()
        
        # Process through surgical negotiator
        result = await negotiator.handle_lead(
            user_id=user_id,
            message=msg["user"],
            user_info=msg["info"]
        )
        
        print(f"🤖 Oisha: {result['response']}")
        print()
        print(f"📊 TAHLIL:")
        print(f"   Stage: {result['stage']}")
        print(f"   Intent: {result['assessment']['intent']}")
        print(f"   Objection: {result['assessment']['objection']}")
        print(f"   Close Probability: {result['assessment']['close_probability']:.0%}")
        print(f"   Autonomy Mode: {result['assessment']['autonomy_mode']}")
        
        if result.get('actions'):
            print(f"\n⚡ ACTIONS:")
            for action in result['actions']:
                print(f"   • {action['type']}")
        
        if result.get('contract'):
            print(f"\n📄 CONTRACT GENERATED!")
            print(f"   ID: {result['contract']['contract_id']}")
            print(f"   Risk: {result['contract']['risk_assessment']['level']}")
            print(f"   Requires Approval: {result['contract']['risk_assessment']['requires_approval']}")
        
        print(f"\n⏸️  Davom etish uchun ENTER...")
        input()
    
    # Final summary
    print(f"\n{'=' * 60}")
    print("📊 YAKUNIY NATIJA")
    print(f"{'=' * 60}")
    
    dashboard = negotiator.get_dashboard()
    print(f"\nPipeline Stats:")
    for key, value in dashboard['summary'].items():
        print(f"   {key}: {value}")
    
    print(f"\nActive Deals: {len(dashboard['active_negotiations'])}")
    print(f"Requires Human: {len(dashboard['requires_attention'])}")
    
    print(f"\n{'=' * 60}")
    print("✅ DEMO TUGALLANDI")
    print(f"{'=' * 60}")


async def demo_contract_generation():
    """Shartnoma yaratish demo"""
    
    from src.agents import ContractGenerator, RiskAssessor
    
    print("=" * 60)
    print("📄 CONTRACT GENERATION DEMO")
    print("=" * 60)
    
    contract_gen = ContractGenerator()
    risk = RiskAssessor()
    
    # Test contract
    contract = contract_gen.generate_contract(
        service_type="branding",
        client_data={
            "name": "Test Company LLC",
            "phone": "+998 90 123 45 67",
            "email": "test@company.uz",
            "user_id": "test_123"
        },
        deal_data={
            "value": 7500,
            "scope": ["Logo dizayn", "Brandbook", "Guidelines", "Social media kit"],
            "timeline_days": 21,
            "guarantees": ["30 kunlik bepul tuzatish", "Sifat kafolati"]
        }
    )
    
    print(f"\n📝 Contract ID: {contract['contract_id']}")
    print(f"💰 Value: ${contract['variables']['TOTAL_PRICE']}")
    print(f"📅 Timeline: {contract['variables']['TIMELINE']}")
    print(f"⚠️  Requires Approval: {contract['requires_approval']}")
    
    print(f"\n{'─' * 60}")
    print("SHARTNOMA MATNI (boshlang'ich qismi):")
    print(f"{'─' * 60}")
    print(contract['text'][:500] + "...")
    
    # Risk assessment
    print(f"\n{'─' * 60}")
    print("🔍 RISK ASSESSMENT:")
    print(f"{'─' * 60}")
    
    risk_assessment = risk.assess_deal_risk(
        deal_value=7500,
        client_history={"previous_deals": 0},
        negotiation_flags=["price_pressure", "competitive_pressure"],
        service_complexity="medium"
    )
    
    print(f"Risk Score: {risk_assessment['score']:.2f}/1.0")
    print(f"Level: {risk_assessment['level'].upper()}")
    print(f"Autonomy Allowed: {risk_assessment['autonomy_allowed']}")
    print(f"Requires Approval: {risk_assessment['requires_approval']}")
    
    print(f"\n⚠️  Risk Factors:")
    for factor in risk_assessment['breakdown']:
        print(f"   • {factor['factor']}: {factor['weight']} ({factor['level']})")
    
    print(f"\n💡 Recommendations:")
    for rec in risk_assessment['recommendations']:
        print(f"   → {rec}")
    
    print(f"\n📋 Approval Requirements:")
    for req in risk.get_approval_requirements(risk_assessment):
        print(f"   ✓ {req}")


async def demo_pipeline_management():
    """Pipeline boshqaruvi demo"""
    
    from src.agents import get_lifecycle_manager, DealStage, DealPriority
    
    print("=" * 60)
    print("📊 PIPELINE MANAGEMENT DEMO")
    print("=" * 60)
    
    lifecycle = get_lifecycle_manager()
    
    # Create test deals
    deals = [
        ("lead_001", "branding", 5000, DealStage.NEW),
        ("lead_002", "web", 8000, DealStage.QUALIFIED),
        ("lead_003", "marketing", 3000, DealStage.PROPOSAL),
        ("lead_004", "branding", 15000, DealStage.NEGOTIATION),
        ("lead_005", "web", 12000, DealStage.COMMITMENT),
    ]
    
    print("\n🏗️  Creating test deals...")
    for user_id, service, value, stage in deals:
        deal = lifecycle.create_deal(
            user_id=user_id,
            service_type=service,
            source="demo"
        )
        deal.value = value
        deal.priority = DealPriority.HOT if value > 10000 else DealPriority.WARM
        
        if stage != DealStage.NEW:
            lifecycle.advance_stage(deal.id, stage, "Demo initialization")
        
        print(f"   ✅ {deal.id}: {service} @ ${value} → {stage.value}")
    
    # Get stats
    print(f"\n{'─' * 60}")
    print("📈 PIPELINE STATISTICS:")
    print(f"{'─' * 60}")
    
    stats = lifecycle.get_pipeline_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                if v > 0:
                    print(f"   {k}: {v}")
        else:
            print(f"{key}: {value}")
    
    # Run automation cycle
    print(f"\n{'─' * 60}")
    print("⚙️  RUNNING AUTOMATION CYCLE:")
    print(f"{'─' * 60}")
    
    actions = await lifecycle.run_automation_cycle()
    
    if actions:
        for action in actions:
            print(f"   ⚡ {action['rule']} → {action['action']}")
    else:
        print("   (No automation rules triggered)")
    
    # Export report
    print(f"\n{'─' * 60}")
    print("📄 PIPELINE REPORT:")
    print(f"{'─' * 60}")
    print(lifecycle.export_pipeline_report())


async def main():
    """Asosiy demo funksiyasi"""
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🤖 OISHA-OS IDEAL AI AGENT                          ║
║        Autonomous Negotiations System                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    print("\nDemo variantlar:")
    print("1. 🗣️  Full Conversation Demo (yangi lead → closing)")
    print("2. 📄 Contract Generation Demo")
    print("3. 📊 Pipeline Management Demo")
    print("4. 🚀 All Demos (barchasi)")
    print("0. ❌ Chiqish")
    
    choice = input("\nTanlang (1-4, 0): ").strip()
    
    try:
        if choice == "1":
            await demo_new_lead()
        elif choice == "2":
            await demo_contract_generation()
        elif choice == "3":
            await demo_pipeline_management()
        elif choice == "4":
            await demo_new_lead()
            print("\n" + "="*60)
            input("\nDavom etish uchun ENTER...")
            await demo_contract_generation()
            print("\n" + "="*60)
            input("\nDavom etish uchun ENTER...")
            await demo_pipeline_management()
        elif choice == "0":
            print("Chiqish...")
            return
        else:
            print("Noto'g'ri tanlov")
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
