"""
Branding Project End-to-End Demo
Mijoz uchun to'liq checklist demo
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.core.service_configurator import (
    get_service_configurator,
    ServiceType
)
from src.services.core.project_phases import (
    get_project_phase_manager,
    PhaseStatus
)
from src.services.core.client_project_checklist import (
    get_client_project_manager,
    create_branding_project
)


async def demo_service_configuration():
    """Xizmatlarni sozlash demo"""
    
    print("="*70)
    print("📦 JON.BRANDING - XIZMATLAR DEMO")
    print("="*70)
    print()
    
    config = get_service_configurator()
    
    # Show available services
    print("📋 MAVJUD XIZMATLAR:")
    print("-"*70)
    
    for svc in config.get_service_options():
        print(f"\n   🎯 {svc['name_uz']}")
        print(f"      Narx: ${svc['price']}")
        print(f"      Muddat: {svc['days']} kun")
        print(f"      Qadamlar: {svc['total_steps']} ta")
        print(f"      Topshiriqlar:")
        for d in svc['deliverables'][:3]:
            print(f"         • {d}")
        if len(svc['deliverables']) > 3:
            print(f"         ... va yana {len(svc['deliverables']) - 3} ta")
    
    print("\n" + "="*70)
    print("📦 TAVSIYA ETILGAN PAKETLAR:")
    print("-"*70)
    
    for pkg in config.get_recommended_packages():
        services_str = ", ".join([s.value for s in pkg['services']])
        print(f"\n   📦 {pkg['name_uz']} ({pkg['name']})")
        print(f"      Narx: ${pkg['price']}")
        print(f"      Muddat: {pkg['days']} kun")
        print(f"      Xizmatlar: {services_str}")
        print(f"      {pkg['description']}")
    
    input("\n⏸️ Davom etish uchun ENTER...")
    print()


async def demo_project_creation():
    """Loyiha yaratish demo"""
    
    print("="*70)
    print("🎯 LOYIHA YARATISH DEMO")
    print("="*70)
    print()
    
    manager = get_client_project_manager()
    
    # Create a project
    print("👤 Mijoz: 'TechStart Uzbekistan'")
    print("📋 Tanlangan xizmatlar:")
    print("   1. Brand Audit")
    print("   2. Naming")
    print("   3. Logo Design")
    print("   4. Visual Identity")
    print("   5. Brandbook")
    print()
    
    result = await create_branding_project(
        client_name="TechStart Uzbekistan",
        services=["brand_audit", "naming", "logo", "visual_identity", "brandbook"],
        client_id="client_001",
        client_phone="+998 90 123 45 67",
        assigned_team={
            "hunter": "user_hunter_001",
            "setter": "user_setter_001",
            "closer": "user_closer_001",
            "pm": "user_pm_001",
            "designer": "user_designer_001"
        }
    )
    
    print("✅ LOYIHA YARATILDI!")
    print("-"*70)
    print(f"   📌 ID: {result['project_id']}")
    print(f"   💰 Narx: ${result['total_price']}")
    print(f"   ⏰ Muddat: {result['total_days']} kun")
    print(f"   📊 Qadamlar: {result['total_phases']} ta")
    print(f"   🎁 Chegirma: {'Ha (10%)' if result['discount_applied'] else 'Yoq'}")
    print(f"   📅 Deadline: {result['deadline']}")
    print()
    
    # Store for later use
    return result['project_id']


async def demo_checklist_overview(project_id: str):
    """Checklist umumiy ko'rinishi"""
    
    print("="*70)
    print("📋 LOYIHA CHECKLIST - UMUMIY KO'RINISH")
    print("="*70)
    print()
    
    manager = get_client_project_manager()
    checklist = manager.get_project_checklist(project_id)
    
    if not checklist:
        print("❌ Checklist topilmadi")
        return
    
    print(f"👤 Mijoz: {checklist['client_name']}")
    print(f"📊 Status: {checklist['status']}")
    print(f"📈 Progress: {checklist['progress']['percentage']}%")
    print(f"   ✅ Bajarildi: {checklist['progress']['completed']}")
    print(f"   🟡 Bajarilmoqda: {checklist['progress']['in_progress']}")
    print(f"   ⚪ Kutilmoqda: {checklist['progress']['pending']}")
    print(f"   🔒 Bloklangan: {checklist['progress']['locked']}")
    print()
    
    # Show by role
    print("-"*70)
    print("👥 ROLLAR BO'YICHA QADAMLAR:")
    print("-"*70)
    
    for role, phases in checklist['phases_by_role'].items():
        print(f"\n   {role.upper()} ({len(phases)} ta qadam):")
        for i, phase in enumerate(phases[:3], 1):
            status_emoji = {
                "completed": "✅",
                "in_progress": "🟡",
                "pending": "⚪",
                "locked": "🔒"
            }.get(phase['status'], "⚪")
            print(f"      {status_emoji} {phase['id']}: {phase['name_uz']}")
        if len(phases) > 3:
            print(f"      ... va yana {len(phases) - 3} ta")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()


async def demo_phase_execution(project_id: str):
    """Bosqichlarni bajarish demo"""
    
    print("="*70)
    print("🚀 BOSQICHLAR BAJARISH DEMO")
    print("="*70)
    print()
    
    manager = get_client_project_manager()
    
    # Simulate completing several phases
    phases_to_complete = [
        ("H1", "user_hunter_001", "Hunter"),
        ("H2", "user_hunter_001", "Hunter"),
        ("H3", "user_hunter_001", "Hunter"),
        ("H4", "user_hunter_001", "Hunter"),
        ("H5", "user_hunter_001", "Hunter"),
    ]
    
    for phase_id, user_id, role in phases_to_complete:
        print(f"\n{'─'*70}")
        print(f"👤 {role} bosqichni bajaryapti...")
        print(f"🎯 Qadam: {phase_id}")
        
        # Start phase
        start_result = manager.start_phase(project_id, phase_id, user_id)
        if start_result['success']:
            print(f"   🚀 Bosqich boshlandi")
        
        # Simulate work
        await asyncio.sleep(0.5)
        
        # Complete phase
        complete_result = manager.complete_phase(
            project_id=project_id,
            phase_id=phase_id,
            user_id=user_id,
            notes=f"Demo completion by {role}"
        )
        
        if complete_result['success']:
            print(f"   ✅ Bajarildi!")
            if complete_result.get('unlocked_phases'):
                print(f"   🔓 Ochilgan: {', '.join(complete_result['unlocked_phases'])}")
        
        await asyncio.sleep(0.3)
    
    print()
    print("="*70)
    print("📊 NATIJA:")
    print("-"*70)
    
    checklist = manager.get_project_checklist(project_id)
    print(f"   Progress: {checklist['progress']['percentage']}%")
    print(f"   Keyingi qadam: {checklist['next_phase']['name_uz'] if checklist['next_phase'] else 'Yoq'}")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()


async def demo_dashboard():
    """Dashboard demo"""
    
    print("="*70)
    print("📊 DASHBOARD DEMO")
    print("="*70)
    print()
    
    manager = get_client_project_manager()
    
    dashboard = manager.get_dashboard()
    
    print("📈 UMUMIY STATISTIKA:")
    print("-"*70)
    print(f"   📁 Jami loyihalar: {dashboard['total_projects']}")
    print(f"   🟡 Faol: {dashboard['active_projects']}")
    print(f"   ✅ Yakunlangan: {dashboard['completed_projects']}")
    print(f"   💰 Umumiy qiymat: ${dashboard['total_value']:,}")
    print()
    
    print("📋 BOSQICHLAR:")
    print("-"*70)
    print(f"   🟡 Bajarilmoqda: {dashboard['phases']['active']}")
    print(f"   ⚪ Kutilmoqda: {dashboard['phases']['pending']}")
    print(f"   ✅ Yakunlangan: {dashboard['phases']['completed']}")
    print()
    
    if dashboard['recent_projects']:
        print("🆕 SO'NGGI LOYIHALAR:")
        print("-"*70)
        for proj in dashboard['recent_projects']:
            emoji = {"in_progress": "🟡", "completed": "✅", "new": "🆕"}.get(proj['status'], "⚪")
            print(f"   {emoji} {proj['client']}: ${proj['price']}")
    
    print()
    print("📄 KUNLIK HISOBOT:")
    print("-"*70)
    report = manager.generate_daily_report()
    print(report)


async def main():
    """Asosiy demo"""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     🎯 JON.BRANDING - END-TO-END CHECKLIST SYSTEM               ║
║        Mijoz topishdan loyiha topshirishgacha                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nDemo variantlari:")
    print("1. 📦 Xizmatlarni ko'rish")
    print("2. 🎯 Loyiha yaratish")
    print("3. 📋 Checklist ko'rinishi")
    print("4. 🚀 Bosqichlarni bajarish")
    print("5. 📊 Dashboard")
    print("6. 🚀 Barchasi (1-5)")
    print("0. ❌ Chiqish")
    
    choice = input("\nTanlang (1-6, 0): ").strip()
    
    project_id = None
    
    try:
        if choice == "1":
            await demo_service_configuration()
        
        elif choice == "2":
            project_id = await demo_project_creation()
        
        elif choice == "3":
            if not project_id:
                project_id = input("Loyiha ID: ").strip()
            await demo_checklist_overview(project_id)
        
        elif choice == "4":
            if not project_id:
                project_id = input("Loyiha ID: ").strip()
            await demo_phase_execution(project_id)
        
        elif choice == "5":
            await demo_dashboard()
        
        elif choice == "6":
            await demo_service_configuration()
            print("\n" + "="*70)
            input("\nDavom etish uchun ENTER...")
            project_id = await demo_project_creation()
            print("\n" + "="*70)
            input("\nDavom etish uchun ENTER...")
            await demo_checklist_overview(project_id)
            print("\n" + "="*70)
            input("\nDavom etish uchun ENTER...")
            await demo_phase_execution(project_id)
            print("\n" + "="*70)
            input("\nDavom etish uchun ENTER...")
            await demo_dashboard()
        
        elif choice == "0":
            print("Chiqish...")
        
        else:
            print("Noto'g'ri tanlov")
    
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
