"""Read-only probe for the Oisha Instagram / Meta Graph integration."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional for production envs
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.core.instagram_agent import InstagramGraphClient  # noqa: E402


REQUIRED_ENV = [
    "META_PAGE_ACCESS_TOKEN",
    "META_INSTAGRAM_ACCOUNT_ID",
    "META_PAGE_ID",
    "META_VERIFY_TOKEN",
    "META_APP_SECRET",
]


def _ok_response(data: Dict[str, Any]) -> bool:
    return bool(data.get("ok")) and not data.get("error")


def _summarize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    if _ok_response(data):
        summary: Dict[str, Any] = {"ok": True}
        if "id" in data:
            summary["id"] = data.get("id")
        if "username" in data:
            summary["username"] = data.get("username")
        if isinstance(data.get("data"), list):
            summary["count"] = len(data["data"])
        return summary
    return {
        "ok": False,
        "error": data.get("error") or data.get("status_code") or "unknown_error",
    }


def run_probe(*, live: bool, media_limit: int) -> Dict[str, Any]:
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    missing = [name for name in REQUIRED_ENV if not (os.environ.get(name) or "").strip()]
    graph = InstagramGraphClient()
    result: Dict[str, Any] = {
        "ok": not missing,
        "mode": "live" if live else "config",
        "configured": graph.configured,
        "missing_env": missing,
        "has_instagram_account_id": bool(graph.instagram_account_id),
        "has_page_id": bool(graph.page_id),
        "api_version": graph.api_version,
    }

    if missing or not live:
        return result

    checks = {
        "profile": _summarize_response(graph.get_profile()),
        "media": _summarize_response(graph.list_media(limit=media_limit)),
        "account_insights": _summarize_response(graph.get_account_insights()),
    }
    result["checks"] = checks
    result["ok"] = all(check.get("ok") for check in checks.values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Instagram / Meta Graph config without writing data.")
    parser.add_argument("--live", action="store_true", help="Call Meta Graph read endpoints.")
    parser.add_argument("--media-limit", type=int, default=3, help="Media rows to request in live mode.")
    args = parser.parse_args()

    result = run_probe(live=args.live, media_limit=max(1, min(args.media_limit, 25)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
