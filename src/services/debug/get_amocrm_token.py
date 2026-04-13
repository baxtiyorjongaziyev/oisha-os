from settings import settings
from amocrm_sync import AmoCRMSync

def main():
    if not all([settings.AMOCRM_SUBDOMAIN, settings.AMOCRM_CLIENT_ID, settings.AMOCRM_CLIENT_SECRET, settings.AMOCRM_REDIRECT_URL]):
        print("XATO: config.py da AmoCRM sozlamalari (Subdomain, ID, Secret, Redirect) bo'lishi shart!")
        return

    print("=== AmoCRM Dastlabki Avtorizatsiya ===")
    auth_code = input("AmoCRM integratsiyasidan olingan 'Authorization Code'ni kiriting: ").strip()
    
    if not auth_code:
        print("Xato: Kod kiritilmadi.")
        return

    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    success = amocrm.authorize_initial(auth_code)
    
    if success:
        print("\n✅ MUVAFFAQIYATLI! Token saqlandi (amocrm_token.json).")
        print("Endi bot AmoCRM bilan ishlay oladi.")
    else:
        print("\n❌ XATOLIK! Kod noto'g'ri yoki vaqti o'tib ketgan bo'lishi mumkin.")

if __name__ == "__main__":
    main()
