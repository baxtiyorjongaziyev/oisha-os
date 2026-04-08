import asyncio
import logging
import datetime
from database import Database
from services.crm_service import CRMService
from services.enterprise_reporter import EnterpriseReporter
from airtable_sync import AirtableSync

logging.basicConfig(level=logging.INFO)

async def test_finance_report():
    print("🚀 Testing Finance & CRM (Basic Plan) Reporting...")
    
    db = Database()
    crm = CRMService()
    airtable = AirtableSync()
    
    reporter = EnterpriseReporter(db, crm, airtable)
    
    # 1. Test Daily Report
    print("\n--- Daily Efficiency Report ---")
    daily_report = reporter.get_daily_efficiency_report()
    print(daily_report)
    
    # 2. Test Monthly Integrated Report
    print("\n--- Full Team Efficiency Report (AmoCRM + Finance) ---")
    try:
        team_report = await reporter.get_team_efficiency_report()
        print(team_report)
    except Exception as e:
        print(f"❌ Team Report Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_finance_report())
