"""Check whether the running Oisha instance may execute ERP actions."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_readiness(base_url: str, timeout: float) -> tuple[int, dict]:
    url = f"{base_url.rstrip('/')}/api/system/erp-readiness"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return int(exc.code), json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8080",
        help="Oisha API base URL",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    try:
        status, payload = fetch_readiness(args.url, args.timeout)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERP readiness tekshiruvi ishlamadi: {type(exc).__name__}: {exc}")
        return 2

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if status == 200 and payload.get("ready") is True:
        print("ERP readiness: TAYYOR")
        return 0

    blockers = payload.get("blockers") or ["unknown_blocker"]
    print(f"ERP readiness: BLOKLANGAN ({', '.join(blockers)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
