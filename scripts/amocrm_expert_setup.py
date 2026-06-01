"""AmoCRM Basic Tariff Expert Setup & Optimization Tool.

This script configures your AmoCRM integration, registers the webhook,
and monitors your 500 active leads capacity limit.

Run:
  python scripts/amocrm_expert_setup.py --check-capacity
  python scripts/amocrm_expert_setup.py --register-webhook --url https://your-vps-domain.com/webhook/amocrm
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.amocrm_optimizer import AmoOptimizer
from src.settings import settings


async def run_setup():
    parser = argparse.ArgumentParser(description="AmoCRM Basic Tariff Expert Setup")
    parser.add_argument(
        "--check-capacity",
        action="store_true",
        help="Check active leads count against the 500 limit",
    )
    parser.add_argument(
        "--register-webhook",
        action="store_true",
        help="Register Oisha-OS webhook in your AmoCRM account",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("WEBHOOK_URL"),
        help="The public webhook URL of your Oisha-OS server",
    )
    
    args = parser.parse_args()
    
    print("==================================================================")
    print("[KING] Oisha-OS: AmoCRM Basic Tariff Expert Optimizer [KING]")
    print("==================================================================")
    
    if not settings.AMOCRM_SUBDOMAIN or not settings.AMOCRM_CLIENT_ID:
        print("[X] XATO: AmoCRM sozlamalari topilmadi. .env faylini tekshiring.")
        sys.exit(1)
        
    # Initialize amoCRM sync
    amo_sync = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.AMOCRM_CLIENT_SECRET
            else ""
        ),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    
    optimizer = AmoOptimizer(amo=amo_sync)
    
    # 1. Capacity Check
    if args.check_capacity or (not args.check_capacity and not args.register_webhook):
        print("\n[*] 1. Active Leads Capacity Audit...")
        active_count = optimizer.get_active_leads_count()
        if active_count < 0:
            print("[X] Ochiq bitimlar sonini aniqlab bo'lmadi. API ulanishini tekshiring.")
        else:
            capacity_pct = (active_count / 500) * 100
            print(f"   - Hozirgi aktiv bitimlar soni: {active_count} / 500 ({capacity_pct:.1f}%)")
            
            if active_count >= 450:
                print("   [!] XAVF: CRM to'lib bormoqda! Faol bitimlar soni 500 tadan oshib ketish xavfi bor.")
                print("      Tafsiya: `python scripts/amocrm_expert_cleanup.py --live --move-reactivation`ni ishga tushiring.")
            elif active_count >= 400:
                print("   [!] OGOHLANTIRISH: Sdelkalar soni 80% dan oshdi. Tozalash tavsiya etiladi.")
            else:
                print("   [OK] XAVFSIZ: Sdelkalar soni xavfsiz darajada (Limitning 80% idan past).")
                
    # 2. Webhook Registration
    if args.register_webhook:
        print("\n[*] 2. Webhook Integration Process...")
        webhook_url = args.url
        if webhook_url and not webhook_url.endswith("/webhook/amocrm"):
            if not webhook_url.endswith("/"):
                webhook_url += "/"
            webhook_url += "webhook/amocrm"
            
        if not webhook_url:
            print("   [X] XATO: Webhook URL ko'rsatilmadi. --url argumentini bering yoki WEBHOOK_URL env yozing.")
        else:
            print(f"   - Webhook ro'yxatdan o'tkazilmoqda: {webhook_url}")
            res = await optimizer.setup_native_webhooks(webhook_url)
            if res.get("ok"):
                print(f"   [OK] MUVOFFIQUYAT! Webhook statusi: {res.get('status')}")
                if res.get("webhook"):
                    print(f"      Webhook ID: {res.get('webhook', {}).get('id', 'N/A')}")
            else:
                print(f"   [X] XATO: {res.get('error')}")
                
    # 3. Consulting manual
    print("\n[i] 3. Expert Optimization Manual for Basic Tariff:")
    print(optimizer.get_automation_manual())
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_setup())
