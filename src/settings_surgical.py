"""
Surgical Negotiator Settings
Ideal AI Agent uchun qo'shimcha sozlamalar
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class SurgicalSettings(BaseSettings):
    """
    Oisha-OS Ideal AI Agent sozlamalari

    Buni asosiy settings.py ga qo'shing yoki .env faylga yozing
    """

    # Feature flags
    SURGICAL_MODE: bool = Field(
        default=False, description="Avtonom negotsiatsiya rejimi"
    )

    AUTONOMY_THRESHOLD: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Avtonomiya boshlanish ehtimoli (0.0-1.0)",
    )

    HUMAN_TAKEOVER_THRESHOLD: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Inson nazoratiga o'tish chegarasi"
    )

    # Pricing defaults
    DEFAULT_SERVICE_PRICE_MIN: int = Field(
        default=1000, description="Eng arzon xizmat narxi ($)"
    )

    DEFAULT_SERVICE_PRICE_BASE: int = Field(
        default=5000, description="O'rtacha xizmat narxi ($)"
    )

    DEFAULT_SERVICE_PRICE_MAX: int = Field(
        default=25000, description="Eng qimmat xizmat narxi ($)"
    )

    # Contract settings
    CONTRACT_REQUIRES_APPROVAL_ABOVE: int = Field(
        default=10000,
        description="Shu summadan yuqori bo'lsa tasdiqlash talab qilinadi",
    )

    CONTRACT_DEFAULT_TIMELINE_DAYS: int = Field(
        default=14, description="Standart shartnoma muddati (kun)"
    )

    # Automation settings
    STALE_LEAD_DAYS: int = Field(
        default=3, description="Qaysi kundan keyin lead 'stale' hisoblanadi"
    )

    FOLLOW_UP_DAYS: int = Field(
        default=2, description="Taklifdan keyin follow-up kunlari"
    )

    # Risk assessment weights
    RISK_WEIGHT_PRICE_PRESSURE: float = Field(
        default=0.3, description="Narx bosimi xavf vazni"
    )

    RISK_WEIGHT_COMPETITIVE: float = Field(
        default=0.4, description="Raqobat xavf vazni"
    )

    RISK_WEIGHT_NEGATIVE_SENTIMENT: float = Field(
        default=0.5, description="Salbiy kayfiyat xavf vazni"
    )

    # Notifications
    NOTIFY_ON_HIGH_VALUE_DEAL: bool = Field(
        default=True, description="Katta bitimlar haqida xabar berish"
    )

    HIGH_VALUE_THRESHOLD: int = Field(
        default=15000, description="Katta bitim chegarasi"
    )

    NOTIFY_ON_HUMAN_TAKEOVER: bool = Field(
        default=True, description="Inson nazoratiga o'tganda xabar berish"
    )

    # AI settings
    NEGOTIATION_AI_MODEL: str = Field(
        default="gemini-1.5-flash", description="Negotsiatsiya uchun AI model"
    )

    AI_TEMPERATURE: float = Field(
        default=0.7, ge=0.0, le=1.0, description="AI kreativlik darajasi"
    )

    AI_MAX_TOKENS: int = Field(default=300, description="AI javob maksimal uzunligi")

    # Pipeline settings
    PIPELINE_AUTO_ADVANCE: bool = Field(
        default=True, description="Avtomatik bosqich o'tish"
    )

    PIPELINE_DAILY_REPORT: bool = Field(
        default=True, description="Kunlik hisobot yaratish"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Convenience function to get settings
def get_surgical_settings() -> SurgicalSettings:
    """Surgical settings instance"""
    return SurgicalSettings()


# Example .env entries
ENV_EXAMPLE = """
# Surgical Negotiator Settings
SURGICAL_MODE=true
AUTONOMY_THRESHOLD=0.6
HUMAN_TAKEOVER_THRESHOLD=0.2

# Pricing
DEFAULT_SERVICE_PRICE_MIN=1000
DEFAULT_SERVICE_PRICE_BASE=5000
DEFAULT_SERVICE_PRICE_MAX=25000

# Contract
CONTRACT_REQUIRES_APPROVAL_ABOVE=10000
CONTRACT_DEFAULT_TIMELINE_DAYS=14

# Automation
STALE_LEAD_DAYS=3
FOLLOW_UP_DAYS=2

# Notifications
NOTIFY_ON_HIGH_VALUE_DEAL=true
HIGH_VALUE_THRESHOLD=15000
NOTIFY_ON_HUMAN_TAKEOVER=true

# AI
NEGOTIATION_AI_MODEL=gemini-1.5-flash
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=300

# Pipeline
PIPELINE_AUTO_ADVANCE=true
PIPELINE_DAILY_REPORT=true
"""

if __name__ == "__main__":
    # Print example .env entries
    print(ENV_EXAMPLE)

    # Test settings
    settings = get_surgical_settings()
    print("\nCurrent Settings:")
    print(f"SURGICAL_MODE: {settings.SURGICAL_MODE}")
    print(f"AUTONOMY_THRESHOLD: {settings.AUTONOMY_THRESHOLD}")
    print(f"HIGH_VALUE_THRESHOLD: ${settings.HIGH_VALUE_THRESHOLD}")
