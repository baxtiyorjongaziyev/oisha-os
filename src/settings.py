import os
import structlog
from pathlib import Path
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


def normalize_telegram_chat_id(value):
    """Convert raw supergroup/channel IDs to Telegram's canonical -100... form."""
    if value in (None, ""):
        return value
    try:
        chat_id = int(value)
    except (TypeError, ValueError):
        return value
    digits = str(abs(chat_id))
    if chat_id >= 0 or digits.startswith("100") or len(digits) < 10:
        return chat_id
    return -int(f"100{digits}")


class AppSettings(BaseSettings):
    OWNER_ID: int = 0
    WHITELIST_IDS: list[int] = Field(default_factory=list)
    ENABLE_AUTO_REPLY: bool = False  # Explicit opt-in; private replies stay blocked by default
    # DM'dan avtomatik lead ochish qat'iyligi:
    #   strict   — faqat AI is_lead=true degan xabarlar
    #   balanced — is_lead, yoki biror intent signali, yoki matnda telefon/email (default)
    #   all      — har qanday mazmunli DM (personal/non-customer filtrlari baribir amal qiladi)
    AUTO_LEAD_MODE: str = "balanced"
    # DM'dagi rasmlarni Gemini Vision orqali tahlil qilish
    DM_VISION_ENABLED: bool = True
    AUTORUN_MASS_SYNC: bool = True
    ENABLE_CLOUD_USERBOT: bool = False  # Set to True to enable userbot session
    USERBOT_SESSION_STRING: Optional[SecretStr] = None
    TELEGRAM_MCP_ENABLED: bool = False
    TELEGRAM_MCP_SESSION_STRING: Optional[SecretStr] = None
    TELEGRAM_MCP_UPSTREAM_URL: str = "http://127.0.0.1:8765/mcp"
    TELEGRAM_MCP_APPROVAL_TTL_SECONDS: int = 900
    SALESCOACH_API_URL: str = ""
    SALESCOACH_SERVICE_TOKEN: Optional[SecretStr] = None
    SALESCOACH_ENABLED: bool = False
    TELEGRAM_SALESCOACH_ENABLED: bool = False
    TELEGRAM_SALESCOACH_MODE: str = "shadow"
    TELEGRAM_SALESCOACH_IDLE_SECONDS: int = 600
    SALESCOACH_APPROVER_IDS: list[int] = Field(default_factory=list)
    SURGICAL_MODE: bool = True  # Autonomous negotiations agent — ON by default
    AUTONOMY_THRESHOLD: float = (
        0.55  # Min confidence for auto-send (lowered for proactivity)
    )
    RUNNING_IN_CLOUD: bool = False
    APP_TIMEZONE: str = "Asia/Tashkent"
    BOT_TOKEN: SecretStr = SecretStr("")
    ADMIN_BOT_TOKEN: Optional[SecretStr] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[SecretStr] = None
    TELEGRAM_AI_GUEST_MODE_ENABLED: bool = True
    TELEGRAM_AI_STREAMING_ENABLED: bool = True
    TELEGRAM_BOT_TO_BOT_ENABLED: bool = True
    TELEGRAM_MANAGED_BOTS_ENABLED: bool = False
    TELEGRAM_BOT_RUNTIME_BACKEND: str = "aiogram"
    # polling: this process receives updates; webhook: dedicated HTTPS head;
    # disabled: outbound Bot API is allowed but this process never receives.
    TELEGRAM_BOT_INGRESS_MODE: str = "polling"
    TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED: bool = True
    AIOGRAM_WEBHOOK_BASE_URL: Optional[str] = None
    OISHA_COMMAND_CENTER_DIGEST_ENABLED: bool = False
    OISHA_COMMAND_CENTER_DIGEST_HOUR: int = 9
    OISHA_COMMAND_CENTER_DIGEST_MINUTE: int = 5
    TELEGRAM_MINI_APP_URL: Optional[str] = None
    API_ID: int = 0
    API_HASH: str = ""
    GEMINI_API_KEY: SecretStr = SecretStr("")
    GEMINI_CALL_MODEL: str = "gemini-2.5-flash"
    GEMINI_VISION_MODEL: str = "gemini-2.0-flash"
    FREE_AI_GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GROQ_API_KEY: Optional[SecretStr] = None
    GROQ_TEXT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    CLOUDFLARE_ACCOUNT_ID: Optional[str] = None
    CLOUDFLARE_AI_API_TOKEN: Optional[SecretStr] = None
    CLOUDFLARE_TEXT_MODEL: str = "@cf/meta/llama-3.1-8b-instruct"
    CLOUDFLARE_WHISPER_MODEL: str = "@cf/openai/whisper-large-v3-turbo"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434/api"
    OLLAMA_TEXT_MODEL: str = "qwen2.5:3b"
    VAPI_API_KEY: Optional[SecretStr] = None
    VAPI_PHONE_NUMBER_ID: Optional[str] = None
    ENABLE_VOICE_AGENT: bool = False
    AMOCRM_WEBHOOK_SECRET: Optional[SecretStr] = None
    FREE_AI_PROVIDER_TIMEOUT_SECONDS: int = 45
    ENABLE_PAID_AI_FALLBACK: bool = False
    OPENAI_API_KEY: Optional[SecretStr] = None
    OPENAI_TRANSCRIBE_MODEL: str = "whisper-1"
    OPENAI_TEXT_MODEL: str = "gpt-4o-mini"
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    OPENROUTER_API_KEY: Optional[SecretStr] = None
    OPENROUTER_TEXT_MODEL: str = "meta-llama/llama-3.2-3b-instruct:free"
    # --- Bepul AI providerlar (Gemini kvotasi tugaganda fallback) ---
    NVIDIA_NIM_API_KEY: Optional[SecretStr] = None
    NVIDIA_NIM_MODEL: str = "meta/llama-3.3-70b-instruct"
    TOGETHERAI_API_KEY: Optional[SecretStr] = None
    TOGETHERAI_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    HUGGINGFACE_API_KEY: Optional[SecretStr] = None
    HUGGINGFACE_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"
    CEREBRAS_API_KEY: Optional[SecretStr] = None
    CEREBRAS_MODEL: str = "gpt-oss-120b"
    MISTRAL_API_KEY: Optional[SecretStr] = None
    MISTRAL_MODEL: str = "mistral-small-latest"
    SAMBANOVA_API_KEY: Optional[SecretStr] = None
    SAMBANOVA_MODEL: str = "Meta-Llama-3.3-70B-Instruct"
    AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    AMOCRM_SUBDOMAIN: str = ""
    AMOCRM_CLIENT_ID: str = ""
    AMOCRM_CLIENT_SECRET: Optional[SecretStr] = None
    AMOCRM_REDIRECT_URL: str = "https://localhost"
    AIRTABLE_CLIENT_ID: str = ""
    AIRTABLE_CLIENT_SECRET: Optional[SecretStr] = None
    AIRTABLE_REDIRECT_URI: str = "https://localhost"

    # API auth. src/api/security.py bularni settings'dan o'qiydi; maydon
    # e'lon qilinmasa getattr(...) doim "" qaytaradi va butun HTTP auth
    # (Bearer token, JWT cookie, proxy rol xaritasi) jim ishlamay qoladi.
    # SecretStr emas, chunki iste'molchilar qiymatni to'g'ridan-to'g'ri
    # hmac.compare_digest / jwt.decode ga uzatadi.
    OISHA_API_SECRET: str = ""
    JWT_SECRET: str = ""
    OISHA_SERVICE_TOKENS_JSON: str = ""
    OISHA_PROXY_ROLE_MAP_JSON: str = ""
    AMOCRM_CRON_SECRET: Optional[SecretStr] = None
    ENABLE_AMOCRM_LEAD_ENRICHMENT: bool = True
    AMOCRM_ENRICHMENT_MESSAGE_LIMIT: int = 20
    AMOCRM_ENRICHMENT_REFRESH_HOURS: int = 24
    ENABLE_AMOCRM_CALL_ANALYSIS: bool = True
    AMOCRM_CALL_ANALYSIS_ON_WEBHOOK: bool = False
    ENABLE_AMOCRM_CALL_TASKS: bool = True
    AMOCRM_CALL_TASK_DUE_HOURS: int = 24
    AMOCRM_CALL_ANALYSIS_LIMIT: int = 20
    # Juda qisqa yozuvlar (ovoz pochtasi signali, band ohang, xato raqam)
    # haqiqiy suhbat bo'lmasa ham AI orqali "tahlil qilinib", to'qilgan
    # (hallucination) natija AmoCRM'ga yozilishining oldini oladi.
    AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS: int = 10
    AMOCRM_CALL_BACKFILL_ON_WEBHOOK: bool = True
    AMOCRM_CALL_BACKFILL_INTERVAL_MINUTES: int = 60
    AMOCRM_CALL_BACKFILL_LIMIT: int = 50
    AMOCRM_CALL_MAX_AUDIO_MB: int = 19
    AMOCRM_CALL_TRANSCRIPT_NOTE_CHARS: int = 6000
    MOIZVONKI_EMAIL: Optional[str] = None
    MOIZVONKI_PASSWORD: Optional[SecretStr] = None
    MOIZVONKI_API_KEY: Optional[SecretStr] = None
    AIRTABLE_API_KEY: Optional[SecretStr] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    # Airtable OAuth 2.0 (API key o'rniga to'g'ridan-to'g'ri OAuth token)
    AIRTABLE_OAUTH_CLIENT_ID: Optional[str] = None
    AIRTABLE_OAUTH_CLIENT_SECRET: Optional[SecretStr] = None
    AIRTABLE_ACCESS_TOKEN: Optional[SecretStr] = None
    AIRTABLE_REFRESH_TOKEN: Optional[SecretStr] = None
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
    TASKS_GROUP_ID: Optional[int] = None
    STAGNATION_GROUP_ID: Optional[int] = None
    WOW_SERVICE_GROUP_ID: Optional[int] = None
    HISOBCHI_FINANCE_GROUP_ID: Optional[int] = None                      # Moliya guruh ID (card to'lovlar uchun)
    HISOBCHI_KIRIM_TOPIC_ID: Optional[int] = None                        # Kirim topic ID
    HISOBCHI_CHIQIM_TOPIC_ID: Optional[int] = None                       # Chiqim topic ID
    HISOBCHI_PNL_TOPIC_ID: Optional[int] = None                          # P&L (foyda/zarar) topic ID
    HISOBCHI_CASHFLOW_TOPIC_ID: Optional[int] = None                     # Cashflow topic ID
    HISOBCHI_BALANCE_TOPIC_ID: Optional[int] = None                      # Balance topic ID
    HISOBCHI_QARZDORLIK_TOPIC_ID: Optional[int] = None                   # Qarzdorlik / Debt topic ID

    # Case Publisher & CMS Settings
    JONBRANDING_CHANNEL: str = "jonbranding"
    CMS_WEBHOOK_URL: Optional[str] = None
    ENABLE_CASE_PUBLISHER: bool = True
    
    # CMS / Sanity Publisher
    ENABLE_SANITY_PUBLISHER: bool = True
    AMOCRM_WON_STATUS_ID: int = 142
    SANITY_PROJECT_ID: Optional[str] = None
    SANITY_DATASET: Optional[str] = None
    SANITY_TOKEN: Optional[SecretStr] = None
    RUN_USERBOT_ONLY: bool = False



    # Topic IDs (Forum Groups)
    AMOCRM_URL: Optional[str] = None
    # AMOCRM_CLIENT_ID / AMOCRM_CLIENT_SECRET yuqorida (str / SecretStr) e'lon qilingan.
    # Bu yerda qayta e'lon qilinsa, SecretStr oddiy str bilan almashib,
    # .get_secret_value() chaqiruvlari AttributeError beradi.
    AMOCRM_AUTH_CODE: Optional[str] = None
    AMOCRM_REDIRECT_URI: Optional[str] = None
    
    # AmoCRM Chats API (Wazzup alternative)
    AMOCRM_CHAT_ACCOUNT_ID: Optional[str] = None
    AMOCRM_CHAT_CHANNEL_ID: Optional[str] = None
    AMOCRM_CHAT_SECRET: Optional[str] = None
    CRM_TOPIC_ID: Optional[int] = 1
    TOPIC_CRM_ID: Optional[int] = None
    TOPIC_REPORTS_ID: Optional[int] = None
    TOPIC_TASKS_ID: Optional[int] = None
    TOPIC_MEETINGS_ID: Optional[int] = None
    TOPIC_SELLER_1_LEADS_ID: Optional[int] = None
    TOPIC_SELLER_2_LEADS_ID: Optional[int] = None
    TOPIC_FOLLOWUP_ID: Optional[int] = None
    TOPIC_GENERAL_ID: Optional[int] = None
    TOPIC_KIRIM_ID: Optional[int] = None
    STAGNATION_TOPIC_ID: Optional[int] = None
    WOW_SERVICE_TOPIC_ID: Optional[int] = None
    GDRIVE_OFFLOAD_FOLDER_ID: Optional[str] = None

    GSHEET_ID: Optional[str] = None
    GSHEET_CREDS_FILE: str = "service_account.json"

    # Hisobchi Google Sheets backend
    COMPOSIO_API_KEY: Optional[SecretStr] = None
    FROG_SOURCE: str = "db"  # "db" or "composio"
    COMPOSIO_TRELLO_BOARD_ID: Optional[str] = None
    COMPOSIO_GOOGLE_TASKLIST_ID: Optional[str] = None

    HISOBCHI_GSHEET_ID: Optional[str] = None
    HISOBCHI_GSHEET_CREDS_FILE: Optional[str] = None
    HISOBCHI_PNL_WORKSHEET_GID: Optional[int] = None
    HISOBCHI_TRACKING_START_DATE: str = "2026-08-01"

    # Meta Graph API settings (Instagram)
    META_VERIFY_TOKEN: Optional[SecretStr] = None
    META_PAGE_ACCESS_TOKEN: Optional[SecretStr] = None
    META_APP_SECRET: Optional[SecretStr] = None
    META_INSTAGRAM_USER_ID: Optional[str] = None
    META_INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    INSTAGRAM_REPORT_AIRTABLE_TABLE: Optional[str] = None

    # Google Analytics 4
    GA4_PROPERTY_ID: Optional[str] = None
    GA4_CREDENTIALS_JSON: Optional[SecretStr] = None

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
        "\n\n[AGENTIC OPS] Suhbat davomida aniq topshiriqlar berilsa yoki kelishilsa, "
        "avtomatik ravishda [TASK: title=...|assigned_to=...|deadline=...] formatida "
        "javob oxirida vazifa yarating."
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
            "TELEGRAM_MCP_SESSION_STRING",
            "TELEGRAM_WEBHOOK_SECRET",
            "AIOGRAM_WEBHOOK_BASE_URL",
            "TELEGRAM_MINI_APP_URL",
            "OPENAI_API_KEY",
            "GROQ_API_KEY",
            "CLOUDFLARE_ACCOUNT_ID",
            "CLOUDFLARE_AI_API_TOKEN",
            "DEEPSEEK_API_KEY",
            "OPENROUTER_API_KEY",
            "NVIDIA_NIM_API_KEY",
            "TOGETHERAI_API_KEY",
            "VAPI_API_KEY",
            "VAPI_PHONE_NUMBER_ID",
            "HUGGINGFACE_API_KEY",
            "CEREBRAS_API_KEY",
            "MISTRAL_API_KEY",
            "SAMBANOVA_API_KEY",
            "AMOCRM_CLIENT_SECRET",
            "AIRTABLE_API_KEY",
            "AIRTABLE_BASE_ID",
            "AIRTABLE_OAUTH_CLIENT_ID",
            "AIRTABLE_OAUTH_CLIENT_SECRET",
            "AIRTABLE_ACCESS_TOKEN",
            "AIRTABLE_REFRESH_TOKEN",
            "TURSO_DATABASE_URL",
            "TURSO_AUTH_TOKEN",
            "AMOCRM_TG_CHAT_FIELD_ID",
            "CRM_GROUP_ID",
            "PROJECTS_GROUP_ID",
            "TEAM_GROUP_ID",
            "TASKS_GROUP_ID",
            "STAGNATION_GROUP_ID",
            "WOW_SERVICE_GROUP_ID",
            "HISOBCHI_FINANCE_GROUP_ID",
            "HISOBCHI_KIRIM_TOPIC_ID",
            "HISOBCHI_CHIQIM_TOPIC_ID",
            "HISOBCHI_PNL_TOPIC_ID",
            "HISOBCHI_CASHFLOW_TOPIC_ID",
            "HISOBCHI_BALANCE_TOPIC_ID",
            "CRM_TOPIC_ID",
            "TOPIC_CRM_ID",
            "TOPIC_REPORTS_ID",
            "TOPIC_TASKS_ID",
            "TOPIC_MEETINGS_ID",
            "TOPIC_SELLER_1_LEADS_ID",
            "TOPIC_SELLER_2_LEADS_ID",
            "TOPIC_FOLLOWUP_ID",
            "TOPIC_GENERAL_ID",
            "TOPIC_KIRIM_ID",
            "STAGNATION_TOPIC_ID",
            "WOW_SERVICE_TOPIC_ID",
            "GSHEET_ID",
            "HISOBCHI_GSHEET_ID",
            "HISOBCHI_GSHEET_CREDS_FILE",
            "HISOBCHI_QARZDORLIK_TOPIC_ID",
            "HISOBCHI_PNL_WORKSHEET_GID",
            "GDRIVE_OFFLOAD_FOLDER_ID",
            "AMOCRM_CRON_SECRET",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "CMS_WEBHOOK_URL",
            "META_VERIFY_TOKEN",
            "META_PAGE_ACCESS_TOKEN",
            "META_APP_SECRET",
            "META_INSTAGRAM_USER_ID",
            "META_INSTAGRAM_ACCOUNT_ID",
            "INSTAGRAM_REPORT_AIRTABLE_TABLE",
            "GA4_PROPERTY_ID",
            "GA4_CREDENTIALS_JSON",
            "SANITY_PROJECT_ID",
            "SANITY_DATASET",
            "SANITY_TOKEN",
        }
        for key in optional_keys:
            if data.get(key) == "":
                data[key] = None
        for key in (
            "CRM_GROUP_ID",
            "PROJECTS_GROUP_ID",
            "TEAM_GROUP_ID",
            "TASKS_GROUP_ID",
            "STAGNATION_GROUP_ID",
            "WOW_SERVICE_GROUP_ID",
            "HISOBCHI_FINANCE_GROUP_ID",
        ):
            data[key] = normalize_telegram_chat_id(data.get(key))
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


    VAULT_PATH: Path = Path(r"C:/Users/baxti/OneDrive/Документы/Obsidian Vault")
    VAULT_GIT_REMOTE: str = "origin"
    VAULT_GIT_BRANCH: str = "master"
    GITHUB_TOKEN: Optional[SecretStr] = None

settings = AppSettings()
logger = structlog.get_logger()
