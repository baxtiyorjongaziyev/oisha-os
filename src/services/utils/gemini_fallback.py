"""
Facade for Gemini fallback utilities.
Delegates to modular subpackage in src.services.utils.gemini_failover.
"""
from src.services.utils.gemini_failover.models import (
    DEFAULT_FALLBACK_MODELS,
    GeminiModelCooldownError,
    reset_model_quota_cooldowns,
    is_quota_error,
    is_transient_error,
    model_candidates,
)
from src.services.utils.gemini_failover.engine import generate_content_with_fallback
from src.services.utils.gemini_failover.providers import (
    _get_secret,
    _get_setting,
    _call_openai_compatible,
    _call_cloudflare,
    _provider_cooling_down,
    _FallbackResponse,
    _non_gemini_fallback,
)

__all__ = [
    "DEFAULT_FALLBACK_MODELS",
    "GeminiModelCooldownError",
    "reset_model_quota_cooldowns",
    "is_quota_error",
    "is_transient_error",
    "model_candidates",
    "generate_content_with_fallback",
    "_get_secret",
    "_get_setting",
    "_call_openai_compatible",
    "_call_cloudflare",
    "_provider_cooling_down",
    "_FallbackResponse",
    "_non_gemini_fallback",
]
