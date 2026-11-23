"""
Adaptive KPI reporting workflows (Bot API 10.1 Rich Messages / 10.4 HTML Widgets).

Sends interactive HTML Widgets in 1-on-1 Owner/user chats (when ``WIDGETS_ENABLED=1``)
with automatic fallback to ``sendRichMessage`` (preserving KPIs, progress, and tables)
if Telegram rejects widgets, or directly uses ``sendRichMessage`` in group chats.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.services.core.telegram.ai_features.models import (
    build_input_rich_message,
    rich_expandable_blockquote,
    rich_paragraph,
    rich_section_heading,
)
from src.services.core.telegram.ai_features.rich_builders import rich_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _KPIReportSpec:
    """Normalized payload shared across widget, rich-message, and text renderers."""

    title: str
    subtitle: str
    kpis: Sequence[Tuple[str, Any]]
    table_headers: Sequence[str]
    table_rows: Sequence[Sequence[Any]]
    numeric_cols: Sequence[int] = ()
    progress_done: int = 0
    progress_total: int = 0
    details_text: Optional[str] = None
    message_thread_id: Optional[int] = None


def _format_kpi_fallback_text(spec: _KPIReportSpec) -> str:
    """Render plain-HTML fallback text when both Widget and Rich Message fail or are off."""
    lines = [f"<b>{spec.title}</b>", spec.subtitle]
    if spec.kpis:
        lines.append(" | ".join(f"{k}: {v}" for k, v in spec.kpis))
    if spec.progress_total > 0:
        lines.append(f"Progress: {spec.progress_done}/{spec.progress_total}")
    if spec.table_headers and spec.table_rows:
        lines.append(" | ".join(str(h) for h in spec.table_headers))
        for row in spec.table_rows:
            lines.append(" | ".join(str(c) for c in row))
    if spec.details_text:
        lines.append(spec.details_text)
    return "\n".join(lines)


def _build_kpi_widget_html(spec: _KPIReportSpec) -> str:
    """Render compact interactive HTML document for Bot API 10.4 ``sendWidget``."""
    from src.services.core.telegram.widgets import templates as wt

    parts = [wt.header(spec.title, spec.subtitle), wt.kpi_row(spec.kpis)]
    if spec.progress_total > 0:
        parts.append(wt.progress("Progress", spec.progress_done, spec.progress_total))
    if spec.table_headers and spec.table_rows:
        parts.append(wt.table(spec.table_headers, spec.table_rows, numeric=spec.numeric_cols))
    parts.append(wt.action_bar([("Tasdiqlash", "ack")]))
    return wt.render_widget(*parts, interactive=True)


async def _send_rich_kpi_message(
    client: Any,
    chat_id: int | str,
    spec: _KPIReportSpec,
) -> Dict[str, Any]:
    """Send Bot API 10.1/10.5 Rich Message preserving heading, KPIs, progress, and table."""
    blocks: List[Dict[str, Any]] = [
        rich_section_heading(spec.title),
        rich_paragraph(spec.subtitle),
    ]
    if spec.kpis:
        blocks.append(rich_paragraph(" • ".join(f"{k}: {v}" for k, v in spec.kpis)))
    if spec.progress_total > 0:
        pct = round((spec.progress_done / spec.progress_total) * 100)
        blocks.append(
            rich_paragraph(f"Progress: {spec.progress_done}/{spec.progress_total} ({pct}%)")
        )
    if spec.table_headers and spec.table_rows:
        blocks.append(
            rich_table(
                spec.table_headers,
                spec.table_rows,
                numeric_cols=spec.numeric_cols,
                is_bordered=True,
                is_striped=True,
                is_compact=True,
            )
        )
    if spec.details_text:
        blocks.append(
            rich_expandable_blockquote([rich_paragraph(spec.details_text)], credit="Oisha-OS")
        )
    rich_msg = build_input_rich_message(blocks=blocks)
    return await client.send_rich_message(
        chat_id,
        rich_msg,
        message_thread_id=spec.message_thread_id,
    )


async def _send_private_kpi_widget(
    client: Any,
    chat_id: int,
    spec: _KPIReportSpec,
) -> Dict[str, Any]:
    """Attempt private HTML Widget delivery with automatic Rich Message then text fallback."""
    from src.services.core.telegram.widgets.client import WidgetClient
    from src.services.core.telegram.widgets.flags import widgets_enabled
    from src.services.core.telegram.widgets.sender import send_widget_or_text

    rich_sent = False

    async def _send_fallback(cid: int | str, txt: str) -> Any:
        nonlocal rich_sent
        if widgets_enabled("kpi_report"):
            try:
                res_rich = await _send_rich_kpi_message(client, cid, spec)
                rich_sent = True
                return res_rich
            except Exception as exc:
                logger.warning("[KPI] Rich message fallback failed: %s", exc)
        return await client.finalize_streamed_message(
            int(cid), txt, message_thread_id=spec.message_thread_id
        )

    res = await send_widget_or_text(
        client=WidgetClient(client),
        chat_id=chat_id,
        module="kpi_report",
        build_html=lambda: _build_kpi_widget_html(spec),
        fallback_text=_format_kpi_fallback_text(spec),
        send_text=_send_fallback,
        caption=f"{spec.title}: {spec.subtitle}"[:200],
        allow_queries=True,
        message_thread_id=spec.message_thread_id,
    )
    mode = "rich" if rich_sent else res.metadata.get("mode")
    return {"ok": res.success, "mode": mode, "tool": res.tool_name}


async def send_oisha_kpi_report(
    client: Any,
    chat_id: int | str,
    *,
    title: str,
    subtitle: str,
    kpis: Sequence[Tuple[str, Any]],
    table_headers: Sequence[str],
    table_rows: Sequence[Sequence[Any]],
    numeric_cols: Sequence[int] = (),
    progress_done: int = 0,
    progress_total: int = 0,
    details_text: Optional[str] = None,
    is_private_chat: bool = True,
    message_thread_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Send interactive HTML Widget (10.4) in private chat or Rich Table (10.1/10.5) in groups."""
    spec = _KPIReportSpec(
        title=title,
        subtitle=subtitle,
        kpis=kpis,
        table_headers=table_headers,
        table_rows=table_rows,
        numeric_cols=numeric_cols,
        progress_done=progress_done,
        progress_total=progress_total,
        details_text=details_text,
        message_thread_id=message_thread_id,
    )
    if is_private_chat and isinstance(chat_id, int) and chat_id > 0:
        return await _send_private_kpi_widget(client, chat_id, spec)

    return await _send_rich_kpi_message(client, chat_id, spec)
