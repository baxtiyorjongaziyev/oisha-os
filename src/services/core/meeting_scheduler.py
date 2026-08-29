"""
Facade for Meeting Scheduler.
Delegates to modular subpackage in src.services.core.meetings.
"""
from src.services.core.meetings import (
    CONFIRMATION_TERMS,
    LEAD_TERMS,
    LOCATION_HINTS,
    MEETING_TERMS,
    TZ,
    ContextMessage,
    MeetingCandidate,
    TelegramMeetingScheduler,
    extract_meeting_candidate,
)

__all__ = [
    "CONFIRMATION_TERMS",
    "LEAD_TERMS",
    "LOCATION_HINTS",
    "MEETING_TERMS",
    "TZ",
    "ContextMessage",
    "MeetingCandidate",
    "TelegramMeetingScheduler",
    "extract_meeting_candidate",
]
