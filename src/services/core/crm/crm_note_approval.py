"""
Facade for CRM Note Approval Flow.
Delegates to modular subpackage in src.services.core.crm.note_approval.
"""
from src.services.core.crm.note_approval.models import (
    MOOD_EMOJI,
    CATEGORY_EMOJI,
    _safe_call_id,
    _approval_key,
    _edit_key,
    _h,
)
from src.services.core.crm.note_approval.formatters import (
    format_approval_message,
    build_inline_keyboard_aiogram,
    build_inline_keyboard_telethon,
)
from src.services.core.crm.note_approval.state import (
    _pending,
    _pending_edit,
    _prune_pending,
    register_pending,
    post_note_to_amocrm,
    post_notes_to_amocrm,
    pop_pending_edit,
    push_pending_edit,
)
from src.services.core.crm.note_approval.handlers import handle_callback
from src.services.core.crm.note_approval.service import CRMNoteApprovalService

__all__ = [
    "MOOD_EMOJI",
    "CATEGORY_EMOJI",
    "_safe_call_id",
    "_approval_key",
    "_edit_key",
    "_h",
    "format_approval_message",
    "build_inline_keyboard_aiogram",
    "build_inline_keyboard_telethon",
    "_pending",
    "_pending_edit",
    "_prune_pending",
    "register_pending",
    "post_note_to_amocrm",
    "post_notes_to_amocrm",
    "pop_pending_edit",
    "push_pending_edit",
    "handle_callback",
    "CRMNoteApprovalService",
]
