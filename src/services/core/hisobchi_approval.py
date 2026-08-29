"""
Facade for Hisobchi Approval.
Delegates to modular subpackage in src.services.core.finance.approval.
"""
from src.services.core.finance.approval import (
    QUICK_CATEGORIES,
    _approval_key,
    _category_key,
    _change_owner_key,
    _edit_key,
    _fmt_money,
    _get_or_load_pending,
    _pending,
    _pending_edit,
    _skip_key,
    build_approval_keyboard,
    build_approval_message,
    build_category_keyboard,
    get_pending_count,
    handle_callback,
    handle_text_reply,
    prune_old_pending,
    register_pending,
    set_pending_edit,
)

__all__ = [
    "QUICK_CATEGORIES",
    "_approval_key",
    "_category_key",
    "_change_owner_key",
    "_edit_key",
    "_fmt_money",
    "_get_or_load_pending",
    "_pending",
    "_pending_edit",
    "_skip_key",
    "build_approval_keyboard",
    "build_approval_message",
    "build_category_keyboard",
    "get_pending_count",
    "handle_callback",
    "handle_text_reply",
    "prune_old_pending",
    "register_pending",
    "set_pending_edit",
]
