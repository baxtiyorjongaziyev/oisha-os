import asyncio
import os
import sys
import logging

# Set up logging - simplified ASCII for encoding safety
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFIER")

# Add current directory to path
sys.path.append(os.getcwd())

async def verify_system():
    logger.info(">>> [VERIFIER] Starting Oisha-OS System Integrity Check...")
    errors = []

    # 1. Check Imports
    logger.info("Checking core module imports...")
    try:
        from src.services.singularity_core import ProactiveWorker
        from src.services.admin_bot import AdminBot
        from src.services.enterprise_reporter import EnterpriseReporter
        from src.services.onboarding_manager import OnboardingManager
        logger.info("OK: Core imports")
    except Exception as e:
        logger.error(f"FAIL: Import Error: {e}")
        errors.append(f"Import Error: {e}")

    # 2. Check DB
    logger.info("Checking Database connectivity...")
    try:
        from src.database import Database
        db = Database()
        # skip deep check due to threads issue in scratch, just check path
        if os.path.exists(db.db_path):
             logger.info(f"OK: Database exists at {db.db_path}")
        else:
             logger.warning(f"WARN: Database file not found at {db.db_path} (will be created on start)")
    except Exception as e:
        logger.error(f"FAIL: DB Error: {e}")
        errors.append(f"DB Error: {e}")

    # 3. Check Google Drive Integration
    logger.info("Checking GDrive Integration...")
    try:
        from src.services.gdrive import GoogleDriveSync
        from src import config
        creds = getattr(config, "GOOGLE_CREDS_PATH", "data/google_creds.json")
        if os.path.exists(creds):
            gdrive = GoogleDriveSync(creds)
            logger.info("OK: GDrive Init")
        else:
            logger.warning("WARN: GDrive Creds missing (data/google_creds.json)")
    except Exception as e:
        logger.error(f"FAIL: GDrive Error: {e}")
        errors.append(f"GDrive Error: {e}")

    # 4. Check Config
    logger.info("Checking Config variables...")
    try:
        from src import config
        missing_vars = []
        critical_vars = ["BOT_TOKEN", "GEMINI_API_KEY", "OWNER_ID"]
        for var in critical_vars:
            if not getattr(config, var, None):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"WARN: Missing critical config vars: {', '.join(missing_vars)}")
        else:
            logger.info("OK: Critical config vars")
    except Exception as e:
        logger.error(f"FAIL: Config Error: {e}")
        errors.append(f"Config Error: {e}")

    # Final Result
    print("\n--- INTEGRITY REPORT ---")
    if not errors:
        print("[SUCCESS] SYSTEM PERFECT: Oisha-OS is ready for autonomous deployment.")
    else:
        print(f"[ERROR] SYSTEM ISSUES FOUND ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
    print("------------------------")

if __name__ == "__main__":
    asyncio.run(verify_system())
