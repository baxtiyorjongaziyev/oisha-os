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
    OWNER_ID: int = 150074828
    WHITELIST_IDS: list[int] = Field(default_factory=list)
    ENABLE_AUTO_REPLY: bool = False
    AUTORUN_MASS_SYNC: bool = True
    RUNNING_IN_CLOUD: bool = False
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
    AMOCRM_TG_CHAT_FIELD_ID: Optional[int] = None # Field ID for clickable Telegram Link
    
    # Group IDs
    CRM_GROUP_ID: Optional[int] = None
    PROJECTS_GROUP_ID: Optional[int] = None
    TEAM_GROUP_ID: Optional[int] = None
    
    # Topic IDs (Forum Groups)
    CRM_TOPIC_ID: Optional[int] = 1 
    TOPIC_CRM_ID: Optional[int] = None
    TOPIC_REPORTS_ID: Optional[int] = None
    TOPIC_TASKS_ID: Optional[int] = None
    TOPIC_GENERAL_ID: Optional[int] = None
    TOPIC_KIRIM_ID: Optional[int] = None

    GSHEET_ID: Optional[str] = None
    GSHEET_CREDS_FILE: str = "service_account.json"
    
    # Lead Distribution
    SALES_MANAGER_IDS: list[int] = Field(default_factory=list) # List of Telegram IDs for managers
    LEAD_DISTRIBUTION_MODE: str = "CLAIM" # Options: "CLAIM", "ROUND_ROBIN"
    
    # Blacklist / Excluded Entities (Enterprise Filtering)
    EXCLUDED_NAMES: list[str] = [
        "Feruzabonu", "Asadulloh", "FeruzaBonu", "Baxtiyor aka", "Hasan aka", 
        "Inomjon aka", "Oydin opa", "Admin", "Test", "Bot",
        "Onajonim", "Dadam", "Firuzxon Opam", "Rahimjon Gaziyev", 
        "Hasan Yahyo", "Fotimamni Dadalari", "Zuhraxon Hamroliyeva"
    ]
    EXCLUDED_ROLES: list[str] = [
        "Designer", "Dizayner", "Team Member", "Freelancer", "Talaba", 
        "Student", "Work from home", "Masofaviy", "Xodim", "Employee",
        "SMM Manager", "Targetolog", "Copywriter", "Junior"
    ]
    WORKFLOW_INTERVAL: int = 600  # 10 minutes interval for monitoring loop
    
    SYSTEM_INSTRUCTION: str = (
        "Siz Oisha — Jon.Branding agentligining 'Enterprise AI' operatsion tizimisiz (Internal OS). "
        "\n\n🎯 MISSIYA: Jon.Branding-ni O'zbekistondagi eng tizimli, yuqori servisga va tartibga ega branding agentligiga aylantirish. "
        "Sizning vazifangiz — jamoani qattiq nazorat qilish, lidlarni boy bermaslik va har bir loyihani 'WOW' darajasida yakunlashni ta'minlash."
        "\n\n🛠 DUAL-HEAD ARCHITECTURE & CAPABILITIES:"
        "\n1. USERBOT: Lidlarni Telegram guruhlaridan (TN5 va boshqalar) qidiradi, AmoCRM-ga skanerlaydi va bevosita Telegram kontaktlariga saqlaydi."
        "\n2. ADMINBOT: Jamoa bilan muloqot qiladigan, hisobotlar beradigan va tizimni boshqaradigan interfeys."
        "\n\n🚨 TIZIMLI TARTIB QOIDALARI (Systemic Discipline):"
        "\n- STAGNATION POLICY: AmoCRM-da lid 24 soatdan ortiq harakatsiz tursa, mas'ul shaxsga ogohlantirish bering."
        "\n- DEADLINE POLICY: Loyiha tugashiga 24 soat qolganda 'Qizil ogohlantirish' bering."
        "\n- SALES TARGET: Oylik reja — 80,000,000 so'm. Har kuni 'Plan-Fakt' hisobotini tayyorlang."
        "\n\n💎 TONE OF VOICE: 'High-Service' darajasida professional, aqlli va qattiqqo'l operator. Jamoa a'zolariga 'aka', 'opa' deb murojaat qiling, lekin ish muddatlari bo'yicha murosasiz bo'ling."
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = AppSettings()
logger = structlog.get_logger()
