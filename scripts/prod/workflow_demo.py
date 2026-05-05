"""
Jon.Branding Mandatory Workflow Demo
Qat'iy tizimni sinash
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.core.mandatory_workflow import (
    MandatoryWorkflowManager,
    get_mandatory_workflow,
    Role,
    TaskStatus
)
from src.services.core.daily_enforcer import (
    DailyEnforcer,
    get_daily_enforcer,
    setup_jon_branding_team
)
from src.services.core.workflow_telegram_bot import (
    WorkflowTelegramBot,
    get_workflow_bot
)


async def demo_workflow():
    """Workflow demo"""
    print("="*60)
    print("🎯 JON.BRANDING MANDATORY WORKFLOW DEMO")
    print("="*60)
    print()
    
    # Initialize
    workflow = get_mandatory_workflow()
    enforcer = await setup_jon_branding_team()
    bot = get_workflow_bot()
    
    # Demo user: Diyor (Hunter)
    user_id = "hunter_001"
    user_name = "Diyor"
    
    print("👤 Demo foydalanuvchi:")
    print(f"   Ism: {user_name}")
    print(f"   Rol: HUNTER (Lead ovlash)")
    print()
    
    # 1. Assign daily tasks
    print("📋 1. Kunlik vazifalar taqsimlanmoqda...")
    print("-"*60)
    
    tasks = workflow.assign_daily_tasks(user_id, user_name, Role.HUNTER)
    
    print(f"   {len(tasks)} ta vazifa tayinlandi:\n")
    for i, task in enumerate(tasks, 1):
        status_emoji = "🔴" if task.status == TaskStatus.MANDATORY else "🚫"
        print(f"   {i}. {status_emoji} {task.step.name}")
        print(f"      ⏱️ {task.step.estimated_time} daqiqa")
        print(f"      📝 {task.step.description}")
        if task.blocked_reason:
            print(f"      🚫 Bloklangan: {task.blocked_reason}")
        print()
    
    input("⏸️ Davom etish uchun ENTER...")
    print()
    
    # 2. Simulate task completion
    print("✅ 2. Vazifalarni bajarish simulyatsiyasi...")
    print("-"*60)
    
    for i, task in enumerate(tasks):
        # Skip blocked tasks
        if task.status == TaskStatus.BLOCKED:
            print(f"   🚫 {task.step.name} - BLOKlangan, o'tkazib yuborilmoqda")
            continue
        
        print(f"\n   🚀 {task.step.name} boshlanmoqda...")
        
        # Start task
        workflow.start_task(task.id, user_id)
        
        # Simulate work time
        await asyncio.sleep(0.5)
        
        # Complete task
        result = workflow.complete_task(
            task.id, 
            user_id, 
            {"note": f"Demo bajarildi", "demo": True}
        )
        
        print(f"   ✅ Bajarildi!")
        
        if result.get("unblocked_tasks"):
            print(f"   🔓 {len(result['unblocked_tasks'])} ta vazifa ochildi!")
        
        if result.get("next_step"):
            print(f"   ➡️ Keyingi: {result['next_step']['name']}")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()
    
    # 3. Check user status
    print("📊 3. Foydalanuvchi statusi...")
    print("-"*60)
    
    status = workflow.get_user_status(user_id)
    
    print(f"   ✅ Bugun bajarildi: {status['completed_today']}")
    print(f"   ⏳ Faol vazifalar: {status['active_tasks']}")
    print(f"   🔴 Majburiy: {status['mandatory_pending']}")
    print(f"   🚫 Bloklangan: {status['blocked_tasks']}")
    
    if status.get("next_mandatory"):
        print(f"\n   📋 Keyingi vazifa:")
        print(f"      {status['next_mandatory']['name']}")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()
    
    # 4. Daily report
    print("📈 4. Kunlik hisobot...")
    print("-"*60)
    
    report = workflow.get_daily_report()
    
    print(f"   Sana: {report['date']}")
    print(f"   Bajarildi: {report['completed_tasks']} ✅")
    print(f"   Muddati o'tgan: {report['overdue_tasks']} ⏰")
    print(f"   Faol foydalanuvchilar: {report['active_users']}")
    
    if report.get('top_performers'):
        print(f"\n   🏆 TOP BAJARUVCHILAR:")
        for performer in report['top_performers'][:3]:
            print(f"      {performer['name']}: {performer['count']} vazifa")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()
    
    # 5. Telegram bot commands
    print("🤖 5. Telegram bot komandalari...")
    print("-"*60)
    
    commands = [
        ("/my_tasks", []),
        ("/status", []),
        ("/report", []),
    ]
    
    for cmd, args in commands:
        print(f"\n   💬 {cmd}")
        response = await bot.handle_command(user_id, cmd.replace("/", ""), args)
        print(f"   🤖 Bot javobi:")
        for line in response.split("\n")[:8]:  # First 8 lines
            print(f"      {line}")
        if len(response.split("\n")) > 8:
            print(f"      ... (yana {len(response.split(chr(10))) - 8} qator)")
    
    print()
    input("⏸️ Davom etish uchun ENTER...")
    print()
    
    # 6. Admin panel
    print("👑 6. Admin paneli...")
    print("-"*60)
    
    # Make user_id an admin for demo
    bot.admins.append(user_id)
    
    response = await bot.handle_command(
        user_id, 
        "admin_panel", 
        [], 
        is_admin=True
    )
    print(response)
    
    print()
    print(f"   👥 Jamoa statusi:")
    team_response = await bot.handle_command(
        user_id,
        "team_status",
        [],
        is_admin=True
    )
    print(team_response)
    
    print()
    print("="*60)
    print("✅ DEMO TUGALLANDI!")
    print("="*60)
    print()
    print("📋 Xulosa:")
    print("   • Har bir a'zo majburiy vazifalar oladi")
    print("   • Vazifalar ketma-ket bajarilishi kerak")
    print("   • Bloklangan vazifalar oldingisi bajarilgacha yopiq")
    print("   • 4 soatdan keyin bajarilmagan vazifa = BLOK")
    print("   • Telegram bot orqali nazorat")
    print("   • Admin to'liq nazorat qiladi")


async def demo_blocking():
    """Bloklash mehanizmini ko'rsatish"""
    print("\n" + "="*60)
    print("🚫 BLOKLASH MEHANIZMI DEMO")
    print("="*60)
    print()
    
    workflow = get_mandatory_workflow()
    
    # Create a user with incomplete tasks
    user_id = "test_user_001"
    user_name = "Test User"
    
    # Assign tasks
    tasks = workflow.assign_daily_tasks(user_id, user_name, Role.HUNTER)
    
    print(f"👤 {user_name} - HUNTER")
    print(f"📋 {len(tasks)} ta vazifa berildi")
    print()
    
    # Don't complete any tasks
    print("⏰ 4 soat o'tdi, lekin vazifalar bajarilmadi...")
    print("-"*60)
    
    # Manually trigger block
    workflow.block_user(user_id, "Vazifalar o'z vaqtida bajarilmagan (4 soat)")
    
    print("🚫 FOYDALANUVCHI BLOKLANDI!")
    print()
    
    # Check status
    status = workflow.get_user_status(user_id)
    print(f"   Status: BLOKlangan")
    print(f"   Sabab: {status['block_reason']}")
    print()
    
    print("📱 Telegram xabari:")
    print("   🚫 Test User, SIZ BLOKLANDINGIZ!")
    print("   'Kunlik rejani olish' vazifasi bajarilmagan.")
    print("   📞 Direktor bilan bog'laning: +998 XX XXX XX XX")
    print()
    
    print("👔 Direktor xabari:")
    print("   🚨 Test User (hunter) BLOKLANDI!")
    print("   Sababi: h_1 vazifasi bajarilmagan")


async def main():
    """Asosiy demo"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎯 JON.BRANDING MANDATORY WORKFLOW SYSTEM            ║
║        Har qadam nazorat ostida!                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    print("\nDemo variantlari:")
    print("1. 📋 To'liq workflow demo")
    print("2. 🚫 Bloklash mehanizmi")
    print("3. 🚀 Barchasi (1+2)")
    print("0. ❌ Chiqish")
    
    choice = input("\nTanlang (1-3, 0): ").strip()
    
    try:
        if choice == "1":
            await demo_workflow()
        elif choice == "2":
            await demo_blocking()
        elif choice == "3":
            await demo_workflow()
            print("\n" + "="*60)
            input("\nDavom etish uchun ENTER...")
            await demo_blocking()
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
