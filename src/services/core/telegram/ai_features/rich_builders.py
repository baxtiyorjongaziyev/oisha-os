"""
Builders and update extractors for Telegram Bot API 9.1–10.5 payloads:
- Native Checklists (Bot API 9.1/9.2): InputChecklist, InputChecklistTask, ChecklistTasksDone
- Styled & Disabled Inline Buttons (Bot API 9.4/10.3): style (danger/success/primary), disabled
- Date-Time Entity Formatting (Bot API 9.5): date_time entity builder
- Rich Message Tables & Button Blocks (Bot API 10.1/10.3): InputRichBlockTable, InputRichBlockButtons
- Ephemeral Message Parameters & Stopped Generation (Bot API 10.3/10.4)
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ALLOWED_BUTTON_STYLES = ("danger", "success", "primary")


def build_input_checklist(
    title: str,
    tasks: Sequence[Tuple[int, str] | Dict[str, Any]],
    *,
    parse_mode: Optional[str] = None,
    others_can_add_tasks: Optional[bool] = None,
    others_can_mark_tasks_as_done: Optional[bool] = True,
) -> Dict[str, Any]:
    """Build an InputChecklist dict (Bot API 9.1, 1–30 tasks, each text 1–100 chars)."""
    clean_title = (title or "").strip()[:255]
    if not clean_title:
        raise ValueError("Checklist title is required (1-255 chars)")
    if not tasks or len(tasks) > 30:
        raise ValueError("Checklist must contain between 1 and 30 tasks")

    built_tasks: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    for item in tasks:
        if isinstance(item, dict):
            task_id = int(item["id"])
            task_text = str(item["text"]).strip()[:100]
            task_pm = item.get("parse_mode")
        else:
            task_id, raw_text = item
            task_id = int(task_id)
            task_text = str(raw_text).strip()[:100]
            task_pm = parse_mode
        if task_id <= 0 or task_id in seen_ids:
            raise ValueError(f"Task id must be positive and unique, got {task_id}")
        if not task_text:
            raise ValueError(f"Task {task_id} text cannot be empty")
        seen_ids.add(task_id)
        entry: Dict[str, Any] = {"id": task_id, "text": task_text}
        if task_pm:
            entry["parse_mode"] = task_pm
        built_tasks.append(entry)

    payload: Dict[str, Any] = {"title": clean_title, "tasks": built_tasks}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if others_can_add_tasks is not None:
        payload["others_can_add_tasks"] = bool(others_can_add_tasks)
    if others_can_mark_tasks_as_done is not None:
        payload["others_can_mark_tasks_as_done"] = bool(others_can_mark_tasks_as_done)
    return payload


def extract_checklist_tasks_done(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract Bot API 9.1 ChecklistTasksDone service message from an Update."""
    message = update.get("message") or update.get("business_message")
    if not isinstance(message, dict):
        return None
    done_obj = message.get("checklist_tasks_done")
    if not isinstance(done_obj, dict):
        return None
    checklist_msg = done_obj.get("checklist_message") or {}
    return {
        "update_id": int(update.get("update_id") or 0),
        "chat": message.get("chat") or {},
        "from_user": message.get("from") or {},
        "checklist_message_id": checklist_msg.get("message_id"),
        "marked_as_done_task_ids": list(done_obj.get("marked_as_done_task_ids") or []),
        "marked_as_not_done_task_ids": list(done_obj.get("marked_as_not_done_task_ids") or []),
    }


def build_styled_inline_button(
    text: str,
    *,
    style: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    copy_text: Optional[str] = None,
    disabled: bool = False,
) -> Dict[str, Any]:
    """Build a Bot API 9.4/10.3 InlineKeyboardButton with color style or DisabledButton."""
    if style is not None and style not in ALLOWED_BUTTON_STYLES:
        raise ValueError(f"Unsupported button style: {style}")
    btn: Dict[str, Any] = {"text": text}
    if style is not None:
        btn["style"] = style
    if icon_custom_emoji_id is not None:
        btn["icon_custom_emoji_id"] = icon_custom_emoji_id
    if disabled:
        btn["disabled"] = {}
        return btn
    if callback_data is not None:
        btn["callback_data"] = callback_data
    elif url is not None:
        btn["url"] = url
    elif copy_text is not None:
        btn["copy_text"] = {"text": copy_text}
    else:
        raise ValueError("One action (callback_data, url, copy_text, or disabled=True) is required")
    return btn


def build_date_time_entity(
    offset: int,
    length: int,
    unix_time: int,
    *,
    date_time_format: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a Bot API 9.5 date_time MessageEntity for localized/relative timestamps."""
    entity: Dict[str, Any] = {
        "type": "date_time",
        "offset": int(offset),
        "length": int(length),
        "unix_time": int(unix_time),
    }
    if date_time_format:
        entity["date_time_format"] = date_time_format
    return entity


def rich_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    numeric_cols: Sequence[int] = (),
    is_bordered: bool = True,
    is_striped: bool = True,
    is_compact: bool = True,
    caption: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an InputRichBlockTable (Bot API 10.1/10.3) with RichBlockTableCell matrix."""
    num_set = set(numeric_cols)
    cells: List[List[Dict[str, Any]]] = []
    if headers:
        header_row = [
            {
                "text": str(h),
                "is_header": True,
                "align": "right" if idx in num_set else "left",
            }
            for idx, h in enumerate(headers)
        ]
        cells.append(header_row)
    for row in rows:
        cells.append(
            [
                {
                    "text": str(val),
                    "align": "right" if idx in num_set else "left",
                }
                for idx, val in enumerate(row)
            ]
        )
    block: Dict[str, Any] = {"type": "table", "cells": cells}
    if is_bordered:
        block["is_bordered"] = True
    if is_striped:
        block["is_striped"] = True
    if is_compact:
        block["is_compact"] = True
    if caption:
        block["caption"] = caption
    return block


def rich_button_row(buttons: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build an InputRichBlockButtons block (Bot API 10.3)."""
    return {"type": "buttons", "buttons": list(buttons)}


def build_ephemeral_parameters(
    *,
    receiver_user_id: Optional[int] = None,
    callback_query_id: Optional[str] = None,
    replace_callback_query_message: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build Bot API 10.3/10.4 EphemeralMessageParameters dict."""
    if receiver_user_id is None and not callback_query_id:
        raise ValueError("Either receiver_user_id or callback_query_id is required")
    params: Dict[str, Any] = {}
    if receiver_user_id is not None:
        params["receiver_user_id"] = int(receiver_user_id)
    if callback_query_id:
        params["callback_query_id"] = str(callback_query_id)
    if replace_callback_query_message is not None:
        params["replace_callback_query_message"] = bool(replace_callback_query_message)
    return params


def extract_stopped_message_generation(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract Bot API 10.3 MessageGenerationStopped update."""
    stopped = update.get("stopped_message_generation")
    if not isinstance(stopped, dict):
        return None
    return {
        "update_id": int(update.get("update_id") or 0),
        "chat": stopped.get("chat") or {},
        "draft_id": stopped.get("draft_id"),
        "date": stopped.get("date"),
    }
