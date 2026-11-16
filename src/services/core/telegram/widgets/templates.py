"""Jon Branding widget design system.

Tiny on purpose: the whole widget must fit in 4 KB after zlib compression, so
there are no external fonts or libraries. Components return HTML fragments;
``render_widget`` wraps them in the shared shell and checks the limits.
"""
from __future__ import annotations

from html import escape
from typing import Iterable, Optional, Sequence, Tuple

from src.services.core.telegram.widgets.limits import (
    MAX_QUERY_DATA_BYTES,
    validate_html,
    validate_state,
)

# Light/dark tokens; accent is the agency green.
BASE_CSS = (
    ":root{--bg:#fff;--fg:#14171a;--mut:#6b7280;--line:#e5e7eb;--card:#f7f8fa;"
    "--acc:#0f9d58;--warn:#d97706;--bad:#dc2626}"
    "@media(prefers-color-scheme:dark){:root{--bg:#17191c;--fg:#f3f4f6;--mut:#9ca3af;"
    "--line:#2b2f35;--card:#1f2226}}"
    "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);"
    "font:14px/1.4 -apple-system,system-ui,sans-serif}"
    ".w{padding:12px}.h{font-weight:700;font-size:16px;margin:0 0 2px}"
    ".s{color:var(--mut);font-size:12px;margin:0 0 10px}"
    ".k{display:flex;gap:8px;margin-bottom:10px}"
    ".k>div{flex:1;background:var(--card);border-radius:10px;padding:8px}"
    ".k b{display:block;font-size:18px}.k span{color:var(--mut);font-size:11px}"
    ".c{background:var(--card);border-radius:10px;padding:8px 10px;margin-bottom:6px}"
    ".c b{display:block}.c span{color:var(--mut);font-size:12px}"
    "table{width:100%;border-collapse:collapse;font-size:13px}"
    "td,th{padding:5px 4px;border-bottom:1px solid var(--line);text-align:left}"
    "th{color:var(--mut);font-weight:500}.r{text-align:right}"
    ".p{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin:4px 0 10px}"
    ".p i{display:block;height:100%;background:var(--acc)}"
    ".ok{color:var(--acc)}.wa{color:var(--warn)}.bad{color:var(--bad)}"
    ".a{display:flex;gap:8px;margin-top:10px}"
    ".a button{flex:1;border:0;border-radius:8px;padding:9px;font:inherit;font-weight:600;"
    "background:var(--acc);color:#fff}.a .n{background:var(--line);color:var(--fg)}"
    "#o{color:var(--mut);font-size:12px;margin-top:6px;min-height:16px}"
)

# Sends data-q of a tapped button through TelegramWidget.request and shows the answer.
ACTION_JS = (
    "document.querySelectorAll('[data-q]').forEach(function(b){"
    "b.addEventListener('click',function(){var o=document.getElementById('o');"
    "o.textContent='...';TelegramWidget.request(b.dataset.q).then("
    "function(a){o.textContent=a.result||'OK'},"
    "function(e){o.textContent='Xato: '+(e&&e.code)})})})"
)

STATUS_CLASS = {"ok": "ok", "warn": "wa", "bad": "bad"}


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def header(title: str, subtitle: Optional[str] = None) -> str:
    out = f"<p class=h>{_e(title)}</p>"
    if subtitle:
        out += f"<p class=s>{_e(subtitle)}</p>"
    return out


def kpi_row(items: Sequence[Tuple[str, object]]) -> str:
    cells = "".join(f"<div><b>{_e(v)}</b><span>{_e(k)}</span></div>" for k, v in items)
    return f"<div class=k>{cells}</div>"


def card_list(items: Iterable[Tuple[str, str]], status: Optional[Sequence[str]] = None) -> str:
    rows = []
    for i, (title, sub) in enumerate(items):
        cls = STATUS_CLASS.get(status[i], "") if status and i < len(status) else ""
        attr = f" class={cls}" if cls else ""
        rows.append(f"<div class=c><b{attr}>{_e(title)}</b><span>{_e(sub)}</span></div>")
    return "".join(rows)


def table(headers: Sequence[str], rows: Iterable[Sequence[object]], numeric: Sequence[int] = ()) -> str:
    num = set(numeric)
    th = "".join(f"<th{' class=r' if i in num else ''}>{_e(h)}</th>" for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(
            f"<td{' class=r' if i in num else ''}>{_e(c)}</td>" for i, c in enumerate(row)
        ) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{th}</tr>{body}</table>"


def progress(label: str, done: int, total: int) -> str:
    pct = 0 if total <= 0 else max(0, min(100, round(done * 100 / total)))
    return f"<span class=s>{_e(label)}: {done}/{total}</span><div class=p><i style=width:{pct}%></i></div>"


def action_bar(actions: Sequence[Tuple[str, str]], secondary: Sequence[int] = ()) -> str:
    """Buttons whose ``query`` (<=64 bytes) goes to the bot as widget_query data."""
    sec = set(secondary)
    for _, q in actions:
        validate_state("query", q, MAX_QUERY_DATA_BYTES)
    buttons = "".join(
        f"<button data-q=\"{_e(q)}\"{' class=n' if i in sec else ''}>{_e(label)}</button>"
        for i, (label, q) in enumerate(actions)
    )
    return f"<div class=a>{buttons}</div><div id=o></div>"


def render_widget(*fragments: str, interactive: bool = False) -> str:
    """Wrap fragments in the shared shell and enforce Telegram size limits."""
    script = f"<script>{ACTION_JS}</script>" if interactive else ""
    html = f"<style>{BASE_CSS}</style><div class=w>{''.join(fragments)}</div>{script}"
    validate_html(html)
    return html
