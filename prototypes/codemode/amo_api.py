"""Read-only AmoCRM facade for Code Mode. Allowlist only; no mutation method is exposed."""
from __future__ import annotations

from typing import Any

AMO_READS = {
    "get_leads": ("status_id?: number; limit?: number; page?: number; with_contacts?: boolean", "Array<Record<string, unknown>>"),
    "get_lead": ("lead_id: number", "Record<string, unknown> | null"),
    "search_leads": ("query: string; limit?: number", "Array<Record<string, unknown>>"),
}
_ARGS = {
    "get_leads": {"status_id", "limit", "page", "with_contacts"},
    "get_lead": {"lead_id"},
    "search_leads": {"query", "limit"},
}


def render_amo_api(namespace: str = "amo") -> str:
    lines = [f"declare const {namespace}: {{"]
    for name, (args, ret) in AMO_READS.items():
        lines.append(f"  {name}(args: {{ {args} }}): Promise<{ret}>;")
    lines.append("};")
    return "\n".join(lines)


async def call_amo(client: Any, method: str, args: dict[str, Any]) -> Any:
    if method not in AMO_READS:
        raise ValueError(f"amo.{method} is not an allowed read")
    unknown = set(args) - _ARGS[method]
    if unknown:  # block passthrough of raw API params (kwargs in get_leads)
        raise ValueError(f"unknown args: {sorted(unknown)}")
    if method == "get_leads":
        args = {**args, "limit": min(int(args.get("limit") or 50), 250)}
    if method == "search_leads":
        args = {**args, "limit": min(int(args.get("limit") or 5), 50)}
    return await getattr(client, method)(**args)
