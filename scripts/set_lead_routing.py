"""CLI tool to view or configure Meta Lead Ads routing mode (inhouse, utc, split)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.services.core.instagram.leadgen_delivery import (
    get_lead_routing_mode,
    set_lead_routing_mode,
    get_next_lead_destination,
)


def print_status() -> None:
    mode = get_lead_routing_mode()
    next_dest = get_next_lead_destination()
    print("=" * 50)
    print("OISHA-OS: META LEADGEN ROUTING CONFIGURATION")
    print("=" * 50)
    print(f"Active Mode:     {mode.upper()}")
    if mode == "inhouse":
        print("Description:     100% Inhouse (UTC Outsource paused)")
    elif mode == "utc":
        print("Description:     100% UTC Outsource (Inhouse paused)")
    else:
        print("Description:     50/50 alternating round-robin")
    print(f"Next Target:     {next_dest}")
    print("=" * 50)


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].lower() in ("status", "info", "show"):
        print_status()
        return 0

    target = args[0].lower().strip()
    if target in ("inhouse", "in-house", "internal"):
        set_lead_routing_mode("inhouse")
        print("SUCCESS: Lead routing mode set to 'inhouse'. All new leads will route to Inhouse.")
    elif target in ("utc", "outsource"):
        set_lead_routing_mode("utc")
        print("SUCCESS: Lead routing mode set to 'utc'. All new leads will route to UTC.")
    elif target in ("split", "50_50", "auto", "reset"):
        set_lead_routing_mode("split")
        print("SUCCESS: Lead routing mode set to 'split'. Alternating 50/50 round-robin restored.")
    else:
        print(f"Unknown mode: '{target}'")
        print("Usage: python scripts/set_lead_routing.py [inhouse|utc|split|status]")
        return 1

    print_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
