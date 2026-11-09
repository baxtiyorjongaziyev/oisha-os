"""Prototype: render MCP tools as a typed TypeScript API (Cloudflare Code Mode style).

Pure function, no I/O. The model sees this small declaration instead of N tool
schemas, then writes one script against it. Execution/sandboxing is NOT here:
every call must still go through GatewayService.call_tool so that read tools stay
automatic and mutations return pending_approval (owner approval).
"""
from __future__ import annotations

import re
from typing import Any

_JS_IDENT = re.compile(r"[^A-Za-z0-9_]")


def _ts_type(schema: dict[str, Any]) -> str:
    if "enum" in schema:
        return " | ".join(repr(v).replace("'", '"') for v in schema["enum"])
    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(_ts_type({**schema, "type": x}) for x in t)
    if t in ("integer", "number"):
        return "number"
    if t == "string":
        return "string"
    if t == "boolean":
        return "boolean"
    if t == "array":
        return f"Array<{_ts_type(schema.get('items') or {})}>"
    if t == "object":
        return _ts_object(schema)
    return "unknown"


def _ts_object(schema: dict[str, Any]) -> str:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not props:
        return "Record<string, unknown>"
    fields = [
        f"{_JS_IDENT.sub('_', k)}{'' if k in required else '?'}: {_ts_type(v or {})}"
        for k, v in props.items()
    ]
    return "{ " + "; ".join(fields) + " }"


def render_api(tools: list[Any], namespace: str = "telegram") -> str:
    lines = [f"declare const {namespace}: {{"]
    for tool in sorted(tools, key=lambda t: t.name):
        schema = getattr(tool, "inputSchema", None) or {}
        desc = (getattr(tool, "description", "") or "").strip().splitlines()
        if desc:
            lines.append(f"  /** {desc[0][:120].replace('*/', '')} */")
        name = _JS_IDENT.sub("_", tool.name)
        lines.append(f"  {name}(args: {_ts_object(schema)}): Promise<unknown>;")
    lines.append("};")
    return "\n".join(lines)
