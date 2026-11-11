#!/usr/bin/env python3
"""Sync OpenClaw and Hermes agents with latest models and personas on the server.

Usage:
    python scripts/sync_agents_runtime.py
"""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import time
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_agents_runtime")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
OPENCLAW_DEPLOY_DIR = DEPLOY_DIR / "openclaw"
HERMES_DEPLOY_DIR = DEPLOY_DIR / "hermes"
HERMES_HOME = pathlib.Path("/home/hermes/.hermes")


def update_openclaw_config_file(config_path: pathlib.Path) -> bool:
    """Update openclaw.json with Gemini 2.5 Flash as primary and Groq as fallback."""
    try:
        data: dict[str, Any] = {}
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        agents = data.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        defaults["model"] = {
            "primary": "google/gemini-3.5-flash-lite",
            "fallbacks": [
                "google/gemini-3.8-flash",
                "groq/llama-3.3-70b-versatile",
            ],
        }

        models = data.setdefault("models", {})
        providers = models.setdefault("providers", {})
        providers.setdefault("google", {"apiKey": {"source": "env", "id": "GEMINI_API_KEY"}})
        providers.setdefault("groq", {"apiKey": {"source": "env", "id": "GROQ_API_KEY"}})

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        logger.info("[OpenClaw] openclaw.json muvaffaqiyatli yangilandi: %s", config_path)
        return True
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("[OpenClaw] openclaw.json yangilashda xatolik (%s): %s", config_path, exc)
        return False


def sync_openclaw_workspace(workspace_dir: pathlib.Path, owner_user: str | None = None) -> bool:
    """Sync Mr.Jon SOUL.md and IDENTITY.md into OpenClaw workspace."""
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        soul_src = OPENCLAW_DEPLOY_DIR / "workspace" / "SOUL.md"
        identity_src = OPENCLAW_DEPLOY_DIR / "workspace" / "IDENTITY.md"

        if soul_src.is_file():
            shutil.copy2(soul_src, workspace_dir / "SOUL.md")
            logger.info("[OpenClaw] Mr.Jon SOUL.md koʻchirildi: %s", workspace_dir / "SOUL.md")

        if identity_src.is_file():
            shutil.copy2(identity_src, workspace_dir / "IDENTITY.md")
            logger.info("[OpenClaw] Mr.Jon IDENTITY.md koʻchirildi: %s", workspace_dir / "IDENTITY.md")

        if owner_user and os.name != "nt":
            subprocess.run(["chown", "-R", f"{owner_user}:{owner_user}", str(workspace_dir)], check=False)
        return True
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("[OpenClaw] Workspace sinxronlashda xatolik (%s): %s", workspace_dir, exc)
        return False


def sync_all_openclaw_installations(base_homes: list[pathlib.Path] | None = None) -> None:
    """Search and sync all openclaw directories on the server."""
    if base_homes is not None:
        possible_homes = base_homes
    else:
        possible_homes = [pathlib.Path.home()]
        if pathlib.Path("/home").is_dir():
            for p in pathlib.Path("/home").iterdir():
                if p.is_dir():
                    possible_homes.append(p)
        if pathlib.Path("/root").is_dir():
            possible_homes.append(pathlib.Path("/root"))

    seen_homes = set()
    for home in possible_homes:
        real_home = home.resolve()
        if real_home in seen_homes:
            continue
        seen_homes.add(real_home)

        oc_dir = real_home / ".openclaw"
        config_path = oc_dir / "openclaw.json"
        if not oc_dir.is_dir() and not config_path.is_file():
            continue

        owner_user = home.name if home.parent.name == "home" else ("root" if home.name == "root" else None)
        logger.info("[OpenClaw] OpenClaw papkasi topildi: %s (user: %s)", oc_dir, owner_user)

        if config_path.is_file():
            update_openclaw_config_file(config_path)

        # Standart va moslashtirilgan workspaceʼlarni yangilash
        workspaces = [
            oc_dir / "workspace" / "oisha",
            oc_dir / "workspace",
            real_home / "openclaw" / "workspace",
        ]
        for ws in workspaces:
            sync_openclaw_workspace(ws, owner_user)

        # Agar openclaw CLI mavjud boʻlsa, config buyrugʻi orqali ham mustahkamlash
        if owner_user and os.name != "nt":
            cmd = (
                "command -v openclaw >/dev/null 2>&1 && "
                'openclaw config set agents.defaults.model.primary "google/gemini-3.5-flash-lite" 2>/dev/null || true'
            )
            subprocess.run(["sudo", "-iu", owner_user, "bash", "-c", cmd], check=False)


def sync_hermes_agent(hermes_dir: pathlib.Path | None = None) -> None:
    """Sync Hermes agent persona and model settings."""
    hermes_home = hermes_dir or HERMES_HOME
    if not hermes_home.is_dir():
        logger.info("[Hermes] %s katalogi topilmadi, oʻtkazib yuborildi.", hermes_home)
        return

    logger.info("[Hermes] Hermes agent sozlanmoqda: %s", hermes_home)
    soul_src = HERMES_DEPLOY_DIR / "SOUL.md"
    if soul_src.is_file():
        soul_dst = hermes_home / "SOUL.md"
        shutil.copy2(soul_src, soul_dst)
        logger.info("[Hermes] Oisha SOUL.md koʻchirildi: %s", soul_dst)
        if os.name != "nt":
            subprocess.run(["chown", "hermes:hermes", str(soul_dst)], check=False)

    if os.name != "nt":
        hermes_cmds = [
            "hermes config set model.provider gemini || true",
            "hermes config set model.default gemini-2.5-flash || true",
        ]
        for c in hermes_cmds:
            subprocess.run(["sudo", "-iu", "hermes", "bash", "-c", c], check=False)

        # hermes-gateway servisni qayta ishga tushirish
        restart_res = subprocess.run(["sudo", "systemctl", "restart", "hermes-gateway"], check=False)
        if restart_res.returncode == 0:
            logger.info("[Hermes] hermes-gateway xizmati qayta ishga tushirildi.")


def ensure_openclaw_gateway_active() -> bool:
    """Poll the gateway until it is considered healthy, else return False."""
    if os.name == "nt":
        return True

    for attempt in range(1, 6):
        pgrep = subprocess.run(["pgrep", "-af", "openclaw.*gateway"], capture_output=True, text=True, check=False)
        if pgrep.stdout.strip():
            logger.info("[OpenClaw] Gateway processlari topildi: %s", pgrep.stdout.strip())
            return True

        status = subprocess.run(
            [
                "sudo",
                "-iu",
                "ubuntu",
                "bash",
                "-c",
                "command -v openclaw >/dev/null 2>&1 && openclaw gateway status 2>&1 || true",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (status.stdout or status.stderr or "").strip()
        if output and any(token in output.lower() for token in ["running", "active", "ready", "healthy"]):
            logger.info("[OpenClaw] Gateway holati: %s", output)
            return True

        if attempt < 5:
            logger.warning("[OpenClaw] Gateway hali ham faol emas, %s/5 qadamda qayta tekshirilmoqda...", attempt)
            time.sleep(2)

    logger.warning("[OpenClaw] Gateway faol holatda emas. Manual tekshiruv kerak.")
    return False


def restart_openclaw_gateway() -> None:
    """Restart or start OpenClaw gateway service and verify it is running."""
    if os.name == "nt":
        return

    logger.info("[OpenClaw] Gateway jarayonini boshqarish...")

    # 1. Systemd servislari bormi tekshirish
    units = ["openclaw-gateway.service", "openclaw.service", "claw.service"]
    for u in units:
        check = subprocess.run(["systemctl", "list-unit-files", u], capture_output=True, text=True, check=False)
        if u in check.stdout:
            logger.info("[OpenClaw] Systemd unit %s topildi, qayta ishga tushirilmoqda...", u)
            subprocess.run(["sudo", "systemctl", "restart", u], check=False)
            if ensure_openclaw_gateway_active():
                return
            break

    # 2. OpenClaw CLI orqali start / restart
    for user in ["ubuntu", "root"]:
        cli_res = subprocess.run(
            [
                "sudo",
                "-iu",
                user,
                "bash",
                "-c",
                "command -v openclaw >/dev/null 2>&1 && "
                "(openclaw gateway restart || openclaw gateway start || openclaw gateway install)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if cli_res.returncode == 0:
            logger.info("[OpenClaw] CLI gateway (%s): %s", user, cli_res.stdout.strip())
            if ensure_openclaw_gateway_active():
                return
            break

    # 3. Agar jarayon hali ham koʻrinmasa, fon rejimida start berish
    time.sleep(1)
    ps_check = subprocess.run(["pgrep", "-af", "openclaw.*gateway"], capture_output=True, text=True, check=False)
    if not ps_check.stdout.strip():
        logger.warning("[OpenClaw] Gateway fon rejimida ishga tushirilmoqda...")
        subprocess.run(
            ["sudo", "-iu", "ubuntu", "bash", "-c", "nohup openclaw gateway run > ~/.openclaw/gateway.log 2>&1 &"],
            check=False,
        )

    # 4. Status va tekshiruv
    if ensure_openclaw_gateway_active():
        return

    status_check = subprocess.run(
        [
            "sudo",
            "-iu",
            "ubuntu",
            "bash",
            "-c",
            "command -v openclaw >/dev/null 2>&1 && openclaw gateway status 2>&1 || true",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if status_check.stdout.strip():
        logger.info("[OpenClaw] Gateway holati:\n%s", status_check.stdout.strip())


def main() -> None:
    logger.info("=== Agentlar (Mr.Jon va Oisha) modellar va personalar sinxronizatsiyasi boshlandi ===")
    sync_all_openclaw_installations()
    sync_hermes_agent()
    restart_openclaw_gateway()
    logger.info("=== Sinxronizatsiya yakunlandi ===")


if __name__ == "__main__":
    main()
