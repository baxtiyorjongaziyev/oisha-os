import os
import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field, model_validator
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
    OWNER_ID: int = 0
    WHITELIST_IDS: list[int] = Field(default_factory=list)
    ENABLE_AUTO_REPLY: bool = True  # Autonomous Telegram replies enabled by default
    AUTORUN_MASS_SYNC: bool = True
    ENABLE_CLOUD_USERBOT: bool = False  # Set to True to enable userbot session
    USERBOT_SESSION_STRING: Optional[SecretStr] = None
    SURGICAL_MODE: bool = True  # Autonomous negotiations agent — ON by default
    AUTONOMY_THRESHOLD: float = (
        0.55  # Min confidence for auto-send (lowered for proactivity)
    )
    RUNNING_IN_CLOUD: bool = False
    APP_TIMEZONE: str = "Asia/Tashkent"
    BOT_TOKEN: SecretStr = SecretStr("")
    ADMIN_BOT_TOKEN: Optional[SecretStr] = None
    API_ID: int = 0
    API_HASH: str = ""
    GEMINI_API_KEY: SecretStr = SecretStr("")
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    AMOCRM_SUBDOMAIN: str = ""
    AMOCRM_CLIENT_ID: str = ""
    AMOCRM_CLIENT_SECRET: Optional[SecretStr] = None
    AMOCRM_REDIRECT_URL: str = "https://localhost"
    AIRTABLE_API_KEY: Optional[SecretStr] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    DATABASE_URL: str = Field(default="bot_database.db")
    TURSO_DATABASE_URL: Optional[str] = None
    TURSO_AUTH_TOKEN: Optional[SecretStr] = None
    AMOCRM_TG_CHAT_FIELD_ID: Optional[int] = (
        None  # Field ID for clickable Telegram Link
    )

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
    GDRIVE_OFFLOAD_FOLDER_ID: Optional[str] = None

    GSHEET_ID: Optional[str] = None
    GSHEET_CREDS_FILE: str = "service_account.json"

    # Lead Distribution
    SALES_MANAGER_IDS: list[int] = Field(
        default_factory=list
    )  # List of Telegram IDs for managers
    LEAD_DISTRIBUTION_MODE: str = "CLAIM"  # Options: "CLAIM", "ROUND_ROBIN"

    # Blacklist / Excluded Entities (Enterprise Filtering)
    EXCLUDED_NAMES: list[str] = [
        "Feruzabonu",
        "Asadulloh",
        "FeruzaBonu",
        "Baxtiyor aka",
        "Hasan aka",
        "Inomjon aka",
        "Oydin opa",
        "Admin",
        "Test",
        "Bot",
        "Onajonim",
        "Dadam",
        "Firuzxon Opam",
        "Rahimjon Gaziyev",
        "Hasan Yahyo",
        "Fotimamni Dadalari",
        "Zuhraxon Hamroliyeva",
    ]
    EXCLUDED_ROLES: list[str] = [
        "Designer",
        "Dizayner",
        "Team Member",
        "Freelancer",
        "Talaba",
        "Student",
        "Work from home",
        "Masofaviy",
        "Xodim",
        "Employee",
        "SMM Manager",
        "Targetolog",
        "Copywriter",
        "Junior",
    ]
    WORKFLOW_INTERVAL: int = 600  # 10 minutes interval for monitoring loop

    SYSTEM_INSTRUCTION: str = (
        "Siz Oisha — Jon.Branding agentligining 'Surgical COO' operatsion tizimisiz (Internal OS). "
        "\n\n🎯 MISSIYA: Agentlikda 100% tizim intizomi, ma'lumotlar tozaligi va har bir soniyani ROI-ga aylantirish. "
        "Sizning vazifangiz — jamoani qat'iy nazorat qilish, xatolarni shafqatsiz fosh qilish va operatsion bo'shliqlarni yopish."
        "\n\n🚨 TONE OF VOICE (Cold Efficiency):"
        "\n- NO FLATTERY (Paxta qo'yish taqiqlanadi): Hech qanday ortiqcha maqtov, 'ruhlanitirish' va hissiy gaplar ishlatmang."
        "\n- SURGICAL: Faqat faktlar, raqamlar va anomaliyalar. Gapni qisqa va mazmunli qiling."
        "\n- CRITICAL: Yutuqlardan ko'ra, xato va xavflarga ko'proq e'tibor qarating."
        "\n- PROFESSIONAL: Muloqotda rasmiy va masofaviy tonni saqlang. 'Aka/Opa' murojaatidan voz keching, faqat Ism yoki Lavozim (Menejer, PM, Asoschi) orqali murojaat qiling."
        "\n\n🛠 CAPABILITIES: CRM Audit, Mission Control (Lead Distribution), Systemic Enforcement."
        "\n\n🚀 AMO_LEAD AUTO-SYNC: Agar foydalanuvchi brending yoki dizayn xizmati bilan qiziqsa va telefon raqamini qoldirsa, "
        "SIZ javobingiz oxirida quyidagi tagni qo'shishingiz SHART (bu ma'lumotni CRM-ga tushiradi):"
        "\n`[AMO_LEAD: name=Ism|phone=+998...|note=Qisqa izoh]`"
        "\n- Ism: Userning ismi."
        "\n- phone: User qoldirgan telefon raqami."
        "\n- note: Qaysi xizmat bilan qiziqyapti, brend nomi nima va h.k."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_env_values(cls, data):
        if not isinstance(data, dict):
            return data
        for key, value in list(data.items()):
            if isinstance(value, str):
                data[key] = value.lstrip("\ufeff").strip()
            elif hasattr(value, "get_secret_value"):
                data[key] = value.get_secret_value().lstrip("\ufeff").strip()

        optional_keys = {
            "ADMIN_BOT_TOKEN",
            "DEEPSEEK_API_KEY",
            "AMOCRM_CLIENT_SECRET",
            "AIRTABLE_API_KEY",
            "AIRTABLE_BASE_ID",
            "TURSO_DATABASE_URL",
            "TURSO_AUTH_TOKEN",
            "AMOCRM_TG_CHAT_FIELD_ID",
            "CRM_GROUP_ID",
            "PROJECTS_GROUP_ID",
            "TEAM_GROUP_ID",
            "CRM_TOPIC_ID",
            "TOPIC_CRM_ID",
            "TOPIC_REPORTS_ID",
            "TOPIC_TASKS_ID",
            "TOPIC_GENERAL_ID",
            "TOPIC_KIRIM_ID",
            "GSHEET_ID",
            "GDRIVE_OFFLOAD_FOLDER_ID",
        }
        for key in optional_keys:
            if data.get(key) == "":
                data[key] = None
        return data

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def missing_runtime_settings(self) -> list[str]:
        missing: list[str] = []
        if not self.BOT_TOKEN.get_secret_value().strip():
            missing.append("BOT_TOKEN")
        if not self.API_ID:
            missing.append("API_ID")
        if not self.API_HASH.strip():
            missing.append("API_HASH")
        if not self.GEMINI_API_KEY.get_secret_value().strip():
            missing.append("GEMINI_API_KEY")
        if not self.AMOCRM_SUBDOMAIN.strip():
            missing.append("AMOCRM_SUBDOMAIN")
        if not self.AMOCRM_CLIENT_ID.strip():
            missing.append("AMOCRM_CLIENT_ID")
        return missing


settings = AppSettings()
logger = structlog.get_logger()
