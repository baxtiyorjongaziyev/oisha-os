#!/usr/bin/env python3
"""Sync Oisha, Mr.Jon (OpenClaw) and Amina (Hermes) personas, Yadro.md and runtimes.

Supports per-bot isolated synchronization and restart so one bot can be updated
or restarted without touching the other two:
    python scripts/sync_agents_runtime.py --bot mrjon
    python scripts/sync_agents_runtime.py --bot amina
    python scripts/sync_agents_runtime.py --bot oisha --restart
    python scripts/sync_agents_runtime.py --bot all --no-restart
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import shutil
import subprocess
import time
from typing import Any, Sequence

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_agents_runtime")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
OISHA_DEPLOY_DIR = DEPLOY_DIR / "oisha"
OPENCLAW_DEPLOY_DIR = DEPLOY_DIR / "openclaw"
HERMES_DEPLOY_DIR = DEPLOY_DIR / "hermes"
HERMES_HOME = pathlib.Path("/home/hermes/.hermes")
OISHA_RUNTIME_DIR = pathlib.Path("/home/deploy/oisha-os")

BOT_ALIASES: dict[str, str] = {
    "oisha": "oisha", "mrjon": "mrjon", "mr.jon": "mrjon", "openclaw": "mrjon",
    "amina": "amina", "hermes": "amina", "all": "all",
}
YADRO_RELATIVE_PATHS: dict[str, pathlib.Path] = {
    "oisha": pathlib.Path("90-AI") / "Bots" / "Oisha" / "Yadro.md",
    "mrjon": pathlib.Path("90-AI") / "Bots" / "Mr.Jon" / "Yadro.md",
    "amina": pathlib.Path("90-AI") / "Bots" / "Amina" / "Yadro.md",
}


def normalize_bot_target(raw: str) -> str:
    """Resolve CLI bot name or alias into canonical target (oisha, mrjon, amina, all)."""
    key = (raw or "all").strip().lower()
    if key not in BOT_ALIASES:
        raise ValueError(f"Nomaʼlum bot nomi: {raw!r}. Ruxsat etilgan: oisha, mrjon, amina, all")
    return BOT_ALIASES[key]


def strip_yaml_frontmatter(text: str) -> str:
    """Remove optional YAML frontmatter block from Obsidian Yadro.md content."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[idx + 1 :]).lstrip("\r\n")
    return text


def _deploy_soul_path_for_bot(bot: str) -> pathlib.Path:
    """Return canonical deploy SOUL.md path for the given bot."""
    mapping = {
        "oisha": OISHA_DEPLOY_DIR / "SOUL.md",
        "mrjon": OPENCLAW_DEPLOY_DIR / "workspace" / "SOUL.md",
        "amina": HERMES_DEPLOY_DIR / "SOUL.md",
    }
    if bot not in mapping:
        raise ValueError(f"Notoʻgʻri bot identifikatori: {bot}")
    return mapping[bot]


def sync_yadro_to_deploy(bot: str, vault_dir: pathlib.Path | None = None) -> bool:
    """One-way sync from Obsidian Vault 90-AI/Bots/<Bot>/Yadro.md to deploy/.../SOUL.md."""
    canonical = normalize_bot_target(bot)
    if canonical == "all":
        results = [sync_yadro_to_deploy(b, vault_dir=vault_dir) for b in ("oisha", "mrjon", "amina")]
        return all(results)
    resolved_vault = vault_dir or (
        pathlib.Path(os.environ["OBSIDIAN_VAULT_DIR"].strip())
        if os.environ.get("OBSIDIAN_VAULT_DIR", "").strip()
        else None
    )
    if resolved_vault is None or not resolved_vault.is_dir():
        return False
    yadro_file = resolved_vault / YADRO_RELATIVE_PATHS[canonical]
    if not yadro_file.is_file():
        logger.warning("[Yadro] %s uchun Yadro.md topilmadi: %s", canonical, yadro_file)
        return False
    soul_body = strip_yaml_frontmatter(yadro_file.read_text(encoding="utf-8"))
    dst = _deploy_soul_path_for_bot(canonical)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(soul_body, encoding="utf-8")
    logger.info("[Yadro] %s Yadro.md -> %s sinxronlandi.", canonical, dst)
    return True



def update_openclaw_config_file(config_path: pathlib.Path) -> bool:
    """Update openclaw.json with Gemini 3.5 Flash as primary and 3.5 Lite / 3 Flash Preview fallbacks."""
    try:
        data: dict[str, Any] = {}
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        agents = data.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        defaults["model"] = {
            "primary": "google/gemini-3.5-flash",
            "fallbacks": [
                "google/gemini-3.5-flash-lite",
                "google/gemini-3-flash-preview",
            ],
        }

        if "models" in data and isinstance(data["models"], dict):
            providers = data["models"].get("providers")
            if isinstance(providers, dict):
                for p_name in ["google", "groq"]:
                    if p_name in providers and isinstance(providers[p_name], dict):
                        if isinstance(providers[p_name].get("apiKey"), dict):
                            del providers[p_name]
                if not providers:
                    del data["models"]["providers"]
            if not data["models"]:
                del data["models"]

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


def _discover_possible_homes(base_homes: list[pathlib.Path] | None) -> list[pathlib.Path]:
    """Return candidate user home directories on the host."""
    if base_homes is not None:
        return base_homes
    homes = [pathlib.Path.home()]
    if pathlib.Path("/home").is_dir():
        homes.extend(p for p in pathlib.Path("/home").iterdir() if p.is_dir())
    if pathlib.Path("/root").is_dir():
        homes.append(pathlib.Path("/root"))
    return homes


def sync_all_openclaw_installations(base_homes: list[pathlib.Path] | None = None) -> None:
    """Search and sync all openclaw directories on the server."""
    seen_homes: set[pathlib.Path] = set()
    for home in _discover_possible_homes(base_homes):
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

        for ws in (oc_dir / "workspace" / "oisha", oc_dir / "workspace", real_home / "openclaw" / "workspace"):
            sync_openclaw_workspace(ws, owner_user)

        if owner_user and os.name != "nt":
            if os.getenv("OISHA_RUN_OPENCLAW_DOCTOR_FIX", "0") == "1":
                try:
                    subprocess.run(
                        ["sudo", "-iu", owner_user, "bash", "-c",
                         "command -v openclaw >/dev/null 2>&1 && openclaw doctor --fix"],
                        check=False, timeout=60,
                    )
                except subprocess.TimeoutExpired:
                    logger.warning("[OpenClaw] Doctor repair timed out for %s", owner_user)
            cmd = (
                "command -v openclaw >/dev/null 2>&1 && "
                'openclaw config set agents.defaults.model.primary "google/gemini-3.5-flash"'
            )
            try:
                subprocess.run(["sudo", "-iu", owner_user, "bash", "-c", cmd], check=False, timeout=30)  # nosec B603
            except subprocess.TimeoutExpired:
                logger.warning("[OpenClaw] Model config timed out for %s", owner_user)


def restart_hermes_gateway() -> bool:
    """Restart ONLY hermes-gateway.service (Amina) without touching Mr.Jon or Oisha."""
    if os.name == "nt":
        return True
    restart_res = subprocess.run(["sudo", "systemctl", "restart", "hermes-gateway"], check=False)
    if restart_res.returncode == 0:
        logger.info("[Hermes] hermes-gateway xizmati qayta ishga tushirildi.")
        return True
    logger.warning("[Hermes] hermes-gateway restart qaytarish kodi: %s", restart_res.returncode)
    return False


def sync_hermes_agent(hermes_dir: pathlib.Path | None = None, *, restart: bool = True) -> None:
    """Sync Amina (Hermes) agent persona and model settings."""
    hermes_home = hermes_dir or HERMES_HOME
    if not hermes_home.is_dir():
        logger.info("[Hermes] %s katalogi topilmadi, oʻtkazib yuborildi.", hermes_home)
        return

    logger.info("[Hermes] Hermes agent sozlanmoqda: %s", hermes_home)
    from scripts.hermes_env_guard import enforce_hermes_telegram_guards, ensure_amina_soul_guards

    enforce_hermes_telegram_guards(hermes_home / ".env")
    soul_src = HERMES_DEPLOY_DIR / "SOUL.md"
    if soul_src.is_file():
        soul_dst = hermes_home / "SOUL.md"
        shutil.copy2(soul_src, soul_dst)
        ensure_amina_soul_guards(soul_dst)
        logger.info("[Hermes] Amina SOUL.md koʻchirildi: %s", soul_dst)
        if os.name != "nt":
            subprocess.run(["chown", "hermes:hermes", str(soul_dst)], check=False)

    if os.name != "nt":
        for c in (
            "hermes config set model.provider gemini || true",
            "hermes config set model.default gemini-3.5-flash-lite || true",
        ):
            subprocess.run(["sudo", "-iu", "hermes", "bash", "-c", c], check=False)
        if restart:
            restart_hermes_gateway()


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
            ["sudo", "-iu", "ubuntu", "bash", "-c",
             "command -v openclaw >/dev/null 2>&1 && openclaw gateway status 2>&1 || true"],
            capture_output=True, text=True, check=False,
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
    """Restart or start ONLY OpenClaw gateway service (Mr.Jon)."""
    if os.name == "nt":
        return

    logger.info("[OpenClaw] Gateway jarayonini boshqarish...")
    for u in ("openclaw-gateway.service", "openclaw.service", "claw.service"):
        check = subprocess.run(["systemctl", "list-unit-files", u], capture_output=True, text=True, check=False)
        if u in check.stdout:
            logger.info("[OpenClaw] Systemd unit %s topildi, qayta ishga tushirilmoqda...", u)
            subprocess.run(["sudo", "systemctl", "restart", u], check=False)
            if ensure_openclaw_gateway_active():
                return
            break

    for user in ("ubuntu", "root"):
        cli_res = subprocess.run(
            ["sudo", "-iu", user, "bash", "-c",
             "command -v openclaw >/dev/null 2>&1 && "
             "(openclaw gateway restart || openclaw gateway start || openclaw gateway install)"],
            capture_output=True, text=True, check=False,
        )
        if cli_res.returncode == 0:
            logger.info("[OpenClaw] CLI gateway (%s): %s", user, cli_res.stdout.strip())
            if ensure_openclaw_gateway_active():
                return
            break

    time.sleep(1)
    ps_check = subprocess.run(["pgrep", "-af", "openclaw.*gateway"], capture_output=True, text=True, check=False)
    if not ps_check.stdout.strip():
        logger.warning("[OpenClaw] Gateway fon rejimida ishga tushirilmoqda...")
        subprocess.run(
            ["sudo", "-iu", "ubuntu", "bash", "-c", "nohup openclaw gateway run > ~/.openclaw/gateway.log 2>&1 &"],
            check=False,
        )

    if ensure_openclaw_gateway_active():
        return
    status_check = subprocess.run(
        ["sudo", "-iu", "ubuntu", "bash", "-c",
         "command -v openclaw >/dev/null 2>&1 && openclaw gateway status 2>&1 || true"],
        capture_output=True, text=True, check=False,
    )
    if status_check.stdout.strip():
        logger.info("[OpenClaw] Gateway holati:\n%s", status_check.stdout.strip())


def restart_oisha_service() -> bool:
    """Restart ONLY oisha.service without touching Mr.Jon or Amina."""
    if os.name == "nt":
        return True
    res = subprocess.run(["sudo", "systemctl", "restart", "oisha.service"], check=False)  # nosec B603
    if res.returncode == 0:
        logger.info("[Oisha] oisha.service qayta ishga tushirildi.")
        return True
    logger.warning("[Oisha] oisha.service restart qaytarish kodi: %s", res.returncode)
    return False


def sync_oisha_agent(runtime_dir: pathlib.Path | None = None, *, restart: bool = False) -> bool:
    """Sync Oisha SOUL.md into runtime deploy directory and optionally restart oisha.service."""
    soul_src = OISHA_DEPLOY_DIR / "SOUL.md"
    target_root = runtime_dir or OISHA_RUNTIME_DIR
    if soul_src.is_file() and target_root.is_dir():
        dst = target_root / "deploy" / "oisha" / "SOUL.md"
        if soul_src.resolve() != dst.resolve():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(soul_src, dst)
            logger.info("[Oisha] Oisha SOUL.md koʻchirildi: %s", dst)
    if restart:
        return restart_oisha_service()
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Per-bot persona and runtime synchronizer")
    parser.add_argument("--bot", default="all", help="Target bot: oisha | mrjon | amina | all")
    parser.add_argument("--no-restart", action="store_true", help="Sync files without restarting services")
    parser.add_argument("--restart", action="store_true", help="Force restart of the selected bot service")
    parser.add_argument("--vault-dir", type=pathlib.Path, default=None, help="Obsidian Vault root directory")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(list(argv) if argv is not None else [])
    target = normalize_bot_target(args.bot)
    do_restart = not args.no_restart
    logger.info("=== Agent sinxronizatsiyasi boshlandi (target=%s, restart=%s) ===", target, do_restart)
    sync_yadro_to_deploy(target, vault_dir=args.vault_dir)
    if target in {"oisha", "all"}:
        sync_oisha_agent(restart=bool(args.restart and do_restart))
    if target in {"mrjon", "all"}:
        sync_all_openclaw_installations()
        if do_restart:
            restart_openclaw_gateway()
    if target in {"amina", "all"}:
        sync_hermes_agent(restart=do_restart)
    logger.info("=== Sinxronizatsiya yakunlandi (target=%s) ===", target)


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
