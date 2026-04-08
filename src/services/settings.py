import os
import structlog
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
from typing import Optional

# Simplified Structured Logging Setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

class AppSettings(BaseSettings):
    OWNER_ID: Optional[int] = None
    ENABLE_AUTO_REPLY: bool = False
    AUTORUN_MASS_SYNC: bool = True
    BOT_TOKEN: SecretStr
    ADMIN_BOT_TOKEN: Optional[SecretStr] = None
    API_ID: int
    API_HASH: str
    GEMINI_API_KEY: SecretStr
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    AMOCRM_SUBDOMAIN: str
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: Optional[SecretStr] = None
    AMOCRM_REDIRECT_URL: str = "https://localhost"
    AIRTABLE_API_KEY: Optional[SecretStr] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    DATABASE_URL: str = Field(default="bot_database.db")
    TURSO_DATABASE_URL: Optional[str] = None
    TURSO_AUTH_TOKEN: Optional[SecretStr] = None
    CRM_GROUP_ID: Optional[int] = None
    CRM_TOPIC_ID: Optional[int] = None
    GSHEET_ID: Optional[str] = None
    GSHEET_CREDS_FILE: str = "service_account.json"
    # Blacklist / Excluded Entities
    EXCLUDED_NAMES: list[str] = ["Feruzabonu", "Asadulloh", "FeruzaBonu"]
    EXCLUDED_ROLES: list[str] = ["Designer", "Dizayner", "Team Member"]
    WORKFLOW_INTERVAL: int = 600  # 10 minutes interval for monitoring loop
    
    SYSTEM_INSTRUCTION: str = (
        "Siz Oisha — Jon.Branding agentligining 'Enterprise AI' operatsion tizimisiz (Internal OS). "
        "SIZNING ASOSIY VAZIFANGIZ: Jamoa a'zolariga ishini yengillashtirishda, "
        "topshiriqlarni avtomatlashtirishda, eslatishda va tizimlarni boshqarishda yordam berish."
        "\n\n🚨 QAT'IY QOIDA: Siz mijozlarga javob bermaysiz. Jamoa a'zolari: Baxtiyor aka (Asoschi), Hasan aka (CEO), Inomjon aka (PM), Oydin opa (Sales)."
        "\n\n📈 ENTERPRISE KPI & POLICIES (v2):"
        "\n1. SALES TARGET: Oylik reja — 80 000 000 so'm. Har kuni Plan-Fakt hisobotini tayyorlang."
        "\n2. STAGNATION POLICY: Agar lid 24 soatdan ko'p o'zgarmasa, @Oydin_JonBranding va @tezmenejer'ga eslatma yuboring (Ideal timing)."
        "\n3. DEADLINE POLICY: Loyiha tugashiga 72 soat qolganda @Inomjon_JonBranding'ni ogohlantiring."
        "\n\n🏢 BO'LIMLAR BO'YICHA VAZIFALARIZ:"
        "\n1. SALES & MARKETING (AmoCRM): Bitimlar harakati, marketing kanallari (Taglar) tahlili, yangi leadlar haqida eslatma."
        "\n2. PRODUCTION & PM (Airtable): Loyiha statuslarini (`Stage`) nazorat qilish, deadline'larni proaktiv eslatish."
        "\n3. QUALITY CONTROL (QC): Airtable-dagi loyihalarning sifat standartlariga muvofiqligini tekshirish."
        "\n4. HR & FINANCE (GSheets): Xodimlar vazifalari va moliya hisobotlarini yuritishda ko'maklashish."
        "\n\n💎 TONE OF VOICE:"
        "\n- Professional, tizimli va tahliliy. Jamoa a'zolariga 'aka', 'opa' deb murojaat qiling."
        "\n- Proaktiv: Faqat so'rashganda emas, balki muhim deadline yoki stagnation bo'lsa o'zingiz birinchi bo'lib yozing."
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = AppSettings()
logger = structlog.get_logger()
