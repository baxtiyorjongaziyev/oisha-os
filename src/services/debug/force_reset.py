def force_write(path, content):
    print(f"Force writing {path}...")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.truncate()
    print("Done.")

settings_content = """import os
import structlog
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
from typing import Optional

# Structured Logging Setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

class AppSettings(BaseSettings):
    BOT_TOKEN: SecretStr
    API_ID: int
    API_HASH: str
    GEMINI_API_KEY: SecretStr
    AMOCRM_SUBDOMAIN: str
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: Optional[SecretStr] = None
    AMOCRM_REDIRECT_URI: str = "https://localhost"
    AIRTABLE_API_KEY: Optional[SecretStr] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    DATABASE_URL: str = Field(default="bot_database.db")
    TURSO_DATABASE_URL: Optional[str] = None
    TURSO_AUTH_TOKEN: Optional[SecretStr] = None
    CRM_GROUP_ID: Optional[int] = None
    CRM_TOPIC_ID: Optional[int] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = AppSettings()
logger = structlog.get_logger()
"""

config_content = """import os
from settings import settings

BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
GEMINI_API_KEY = settings.GEMINI_API_KEY.get_secret_value()
API_ID = settings.API_ID
API_HASH = settings.API_HASH

AMOCRM_SUBDOMAIN = settings.AMOCRM_SUBDOMAIN
AMOCRM_CLIENT_ID = settings.AMOCRM_CLIENT_ID
AMOCRM_CLIENT_SECRET = settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None
AMOCRM_REDIRECT_URL = settings.AMOCRM_REDIRECT_URI

AIRTABLE_API_KEY = settings.AIRTABLE_API_KEY.get_secret_value() if settings.AIRTABLE_API_KEY else None
AIRTABLE_BASE_ID = settings.AIRTABLE_BASE_ID

CRM_GROUP_ID = settings.CRM_GROUP_ID
CRM_TOPIC_ID = settings.CRM_TOPIC_ID
"""

force_write("settings.py", settings_content)
force_write("config.py", config_content)

print("Double checking with raw read...")
with open("settings.py", "rb") as f:
    print(f"settings.py length: {len(f.read())}")
with open("config.py", "rb") as f:
    print(f"config.py length: {len(f.read())}")
