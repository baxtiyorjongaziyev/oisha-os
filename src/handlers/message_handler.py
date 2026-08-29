"""
Facade for Telegram Message Handling Pipeline.
Delegates to modular subpackage in src.handlers.msg_pipeline.
"""
from src.handlers.msg_pipeline import (
    _analyze_dm_photo,
    _pop_vision_context,
    _resolve_gemini_client,
    _vision_cache,
    advance_checkpoint,
    process_admin_commands,
    process_ai_reply,
    process_elite_intake,
    process_hisobchi,
    process_media,
    process_voice,
    should_open_lead,
)

__all__ = [
    "advance_checkpoint",
    "process_admin_commands",
    "process_hisobchi",
    "should_open_lead",
    "process_elite_intake",
    "process_voice",
    "_resolve_gemini_client",
    "_analyze_dm_photo",
    "process_media",
    "_vision_cache",
    "_pop_vision_context",
    "process_ai_reply",
]
