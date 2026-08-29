"""
Facade for Call Analyzer.
Delegates to modular implementations in src.services.call_analytics.
Uses rubric_prompt_uz() for evaluation rubric.
"""

from src.services.call_analytics.helpers import (
    ANALYSIS_MARKER,
    CATEGORIES,
    MOODS,
    NO_SPEECH_SENTINEL,
    GeminiQuotaCooldownError,
    _WEEKDAY_UZ,
    _clip,
    _compute_talk_ratio,
    _detect_mime,
    _detect_pauses,
    _extract_amocrm_task_id,
    _extract_json_object,
    _format_timestamp,
    _has_timestamps,
    _looks_like_stt_hallucination,
    _maybe_await,
    _normalise_category,
    _normalise_mood,
    _parse_agreed_datetime,
    _parse_breakdown_time,
    _rubric_applies,
    _speaker_split,
    _strip_timestamps,
    _talk_ratio_verdict,
    _transcript_impossible_for_duration,
)
from src.services.call_analytics.analyzer import CallAnalyzer
from src.services.core.sales_playbook import rubric_prompt_uz

__all__ = [
    "GeminiQuotaCooldownError",
    "CallAnalyzer",
    "ANALYSIS_MARKER",
    "CATEGORIES",
    "MOODS",
    "NO_SPEECH_SENTINEL",
    "_WEEKDAY_UZ",
    "_maybe_await",
    "_detect_mime",
    "_compute_talk_ratio",
    "_looks_like_stt_hallucination",
    "_transcript_impossible_for_duration",
    "_rubric_applies",
    "_parse_agreed_datetime",
    "_clip",
    "_parse_breakdown_time",
    "_extract_amocrm_task_id",
    "_extract_json_object",
    "_normalise_category",
    "_normalise_mood",
    "_speaker_split",
    "_talk_ratio_verdict",
    "_detect_pauses",
    "_format_timestamp",
    "_has_timestamps",
    "_strip_timestamps",
    "_CALL_NOTE_TYPES",
    "_BACKFILL_PAGE_KEY",
    "rubric_prompt_uz",
]
