import asyncio
from settings import settings
from amocrm_sync import AmoCRMSync

async def verify_quality_control():
    print("👸🛡️ Oisha-OS Quality Control Verification...")
    
    # 1. Test Blacklist
    test_name = "Feruzabonu Ganiyeva"
    is_blacklisted = any(name.lower() in test_name.lower() for name in settings.EXCLUDED_NAMES)
    print(f"Test 1 (Blacklist Name): '{test_name}' is blacklisted? -> {is_blacklisted}")
    
    # 2. Test Role Filter
    test_business = "Grafik dizayner xizmati"
    is_role_excluded = any(role.lower() in test_business.lower() for role in settings.EXCLUDED_ROLES)
    print(f"Test 2 (Role Filter): '{test_business}' is excluded? -> {is_role_excluded}")
    
    # 3. Test Deduplication Search (Requires real credentials)
    print("\nAttempting AmoCRM Search (Dedupe check)...")
    try:
        amocrm = AmoCRMSync(
            settings.AMOCRM_SUBDOMAIN,
            settings.AMOCRM_CLIENT_ID,
            settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
            settings.AMOCRM_REDIRECT_URL
        )
        # Search for a likely existing number if any, or just check the method exists
        # print(f"Searching for +998901234567...")
        # contact = amocrm.get_contact_by_phone("+998901234567")
        # print(f"Result: {contact}")
        print("AmoCRM search methods initialized successfully.")
    except Exception as e:
        print(f"AmoCRM check skipped or failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_quality_control())
