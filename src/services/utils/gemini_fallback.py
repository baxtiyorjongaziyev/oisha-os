"""
Facade for Gemini fallback utilities.
Delegates to modular subpackage in src.services.utils.gemini_failover.
"""
from src.services.utils.gemini_failover.models import (
    DEFAULT_FALLBACK_MODELS,
    _MODEL_QUOTA_BLOCKED_UNTIL,
    _PROVIDER_BLOCKED_UNTIL,
    GeminiModelCooldownError,
    _quota_cooldown_seconds,
    _pause_model_for_quota,
    _model_quota_cooling_down,
    _pause_provider,
    _provider_cooling_down,
    reset_model_quota_cooldowns,
    is_quota_error,
    is_transient_error,
    model_candidates,
    _maybe_await,
    _FallbackResponse,
    _FallbackCandidate,
    _FallbackContent,
    _FallbackPart,
)
from src.services.utils.gemini_failover.providers import (
    _extract_messages_from_contents,
    _get_secret,
    _get_setting,
    _call_openai_compatible,
    _call_cloudflare,
    _NON_GEMINI_PROVIDERS,
    _non_gemini_fallback,
)
from src.services.utils.gemini_failover.engine import generate_content_with_fallback

__all__ = [
    "DEFAULT_FALLBACK_MODELS",
    "GeminiModelCooldownError",
    "reset_model_quota_cooldowns",
    "is_quota_error",
    "is_transient_error",
    "model_candidates",
    "generate_content_with_fallback",
]
