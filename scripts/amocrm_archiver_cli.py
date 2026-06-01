#!/usr/bin/env python3
"""amocrm_archiver_cli.py - CRM Archiver command-line interface.

Usage:
  python scripts/amocrm_archiver_cli.py --check-active
  python scripts/amocrm_archiver_cli.py --limit 10 --dry-run
  python scripts/amocrm_archiver_cli.py --limit 10 --live --days 14
"""
import os
import sys
import asyncio
import argparse
import logging
from typing import Dict, Any, List

# Windows terminal emoji/utf-8 compatibility
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Add src folder to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.core.crm_archiver import CRMArchiver
from src.services.core.amocrm_sync import AmoCRMSync

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("archiver_cli")

async def main():
    parser = argparse.ArgumentParser(description="Oisha-OS AmoCRM Archiver and Outreach Reactivation Engine")
    parser.add_argument("--check-active", action="store_true", help="Faol bitimlar soni va limitini tekshirish.")
    parser.add_argument("--limit", type=int, default=10, help="Ushbu batchda arxivlanadigan maksimal bitimlar soni.")
    parser.add_argument("--days", type=int, default=21, help="Stagnatsiya muddati (kunlarda, default: 21).")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Haqiqiy o'zgarishlarsiz faqat hisobot generatsiya qilish (Default).")
    group.add_argument("--live", action="store_true", help="Haqiqiy yozishlarni amalga oshirish (Turso bazaga yozish va AmoCRM statusini o'zgartirish).")

    args = parser.parse_args()

    # Determine real dry_run state
    dry_run = not args.live

    archiver = CRMArchiver()
    await archiver.init_tables()

    if args.check_active:
        print("🔍 AmoCRM faol bitimlar soni tekshirilmoqda...")
        leads = await archiver.fetch_all_active_leads()
        active_count = len(leads)
        print("=" * 60)
        print(f"📊 **AmoCRM FAOL BITIMLAR STATUSI** 📊")
        print(f"• Faol bitimlar soni: {active_count} / 500 limit")
        capacity_pct = (active_count / 500) * 100
        print(f"• Bandlik ko'rsatkichi: {capacity_pct:.1f}%")
        
        if active_count >= 500:
            print("🚨 **DIQQAT!** 500 ta bitim limiti to'lgan! Arxivlash tezkorlik bilan talab etiladi!")
        elif active_count >= 450:
            print("⚠️ **OGOHLANTIRISH!** Limit to'lishiga oz qoldi. Ba'zi stagnant bitimlarni arxivlang.")
        else:
            print("✅ **BARQAROR!** CRM bitimlar soni xavfsiz darajada.")
        print("=" * 60)
        return

    print(f"🌾 **Stagnatsiya threshold:** {args.days} kun")
    print(f"🚜 **Batch limiti:** {args.limit} ta bitim")
    print(f"🔒 **Rejim:** {'DRY-RUN (Faqat hisobot)' if dry_run else '🔴 LIVE (Haqiqiy yozish)'}")
    print("-" * 60)

    stagnant = await archiver.get_stagnant_leads(max_stagnant_days=args.days)
    if not stagnant:
        print("✅ Hech qanday stagnant bitim topilmadi. Arxivlashga hojat yo'q!")
        return

    targets = stagnant[:args.limit]
    print(f"🎯 Arxivlash uchun {len(targets)} ta bitim tanlab olindi:")
    for t in targets:
        updated_date = datetime.datetime.fromtimestamp(t.get('updated_at', 0)).strftime('%Y-%m-%d')
        print(f"  • ID: {t.get('id')} | Nomi: {t.get('name')} | Narxi: {t.get('price', 0):,} so'm | Oxirgi faollik: {updated_date}")

    print("\n🚀 Arxivlash va Outreach generatsiyasi boshlandi...")
    print("-" * 60)

    processed_count = 0
    failed_count = 0

    for lead in targets:
        lead_id = lead.get("id")
        try:
            res = await archiver.archive_lead(lead, dry_run=dry_run)
            if res.get("success"):
                processed_count += 1
                campaign = res.get("campaign", {})
                print(f"✅ [SUCCESS] Lead ID: {lead_id} ({res.get('name')})")
                print(f"  📞 Kontakt: {res.get('contact_name') or 'Noma`lum'} ({res.get('phone') or 'Raqamsiz'})")
                print(f"  💬 3-bosqichli Outreach kampaniyasi:")
                print(f"    1-qadam: {campaign.get('step1')}")
                print(f"    2-qadam: {campaign.get('step2')}")
                print(f"    3-qadam: {campaign.get('step3')}")
                print("-" * 40)
            else:
                failed_count += 1
                print(f"❌ [FAILED] Lead ID: {lead_id} -> {res.get('error')}")
        except Exception as e:
            failed_count += 1
            print(f"❌ [ERROR] Lead ID: {lead_id} -> {e}")

    print("=" * 60)
    print(f"🏁 **ARXIVLASH NATIJALARI** 🏁")
    print(f"• Muvaffaqiyatli: {processed_count} ta")
    print(f"• Xato/Muammo: {failed_count} ta")
    print(f"• Rejim: {'DRY-RUN' if dry_run else 'LIVE'}")
    print("=" * 60)

if __name__ == "__main__":
    import datetime
    asyncio.run(main())
