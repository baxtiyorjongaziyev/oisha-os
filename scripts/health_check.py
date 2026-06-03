import os
import sys
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class ServiceCheck:
    name: str
    url: str
    required: bool = True


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_checks() -> list[ServiceCheck]:
    oisha_url = os.getenv(
        "OISHA_HEALTH_URL",
        "http://127.0.0.1:8080/healthz/",
    )
    checks = [ServiceCheck("Oisha-OS (Production)", oisha_url, required=True)]

    if _env_bool("CHECK_OPTIONAL_SERVICES", False):
        checks.extend(
            [
                ServiceCheck(
                    "JonBranding-Web",
                    os.getenv("JONBRANDING_HEALTH_URL", "https://jonbranding.uz/api/health"),
                    required=False,
                ),
                ServiceCheck(
                    "SalesCoach-AI API",
                    os.getenv(
                        "SALESCOACH_API_HEALTH_URL",
                        "https://salescoach-api-jonbranding-85662071-ea38e.europe-west3.run.app/health",
                    ),
                    required=False,
                ),
                ServiceCheck(
                    "SalesCoach-AI Worker",
                    os.getenv(
                        "SALESCOACH_WORKER_HEALTH_URL",
                        "https://salescoach-worker-jonbranding-85662071-ea38e.europe-west3.run.app/",
                    ),
                    required=False,
                ),
            ]
        )

    return checks


def check_services() -> None:
    all_required_ok = True
    print("Checking Oisha-OS Ecosystem Health...")
    print("-" * 40)

    for check in _build_checks():
        label = "required" if check.required else "optional"
        try:
            response = requests.get(check.url, timeout=10)
            if response.status_code == 200:
                print(f"OK {check.name} ({label}): UP (200)")
            else:
                print(f"WARN {check.name} ({label}): DOWN ({response.status_code})")
                all_required_ok = all_required_ok and not check.required
        except Exception as exc:
            print(f"WARN {check.name} ({label}): ERROR ({type(exc).__name__}: {exc})")
            all_required_ok = all_required_ok and not check.required

    print("-" * 40)
    if all_required_ok:
        print("REQUIRED SERVICES OPERATIONAL")
        return

    print("REQUIRED SERVICES ARE UNSTABLE")
    sys.exit(1)


if __name__ == "__main__":
    check_services()
