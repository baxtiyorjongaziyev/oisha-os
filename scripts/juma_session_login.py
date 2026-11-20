"""Juma tabrigi uchun alohida Telegram sessiyasi (QR-login) yaratish skripti.

Hetzner VPS da interaktiv tarzda ishga tushiriladi (loyiha ichiga yozmaydi):

    set -a && source .env && set +a
    ./venv/bin/python scripts/juma_session_login.py

Telegram -> Sozlamalar -> Qurilmalar -> Qurilmani ulash (Link Desktop Device)
orqali QR skanerlanadi. Yangi session faqat ``/etc/oisha/juma.env`` (0600) ga
``JUMA_SESSION_STRING=...`` koʻrinishida yoziladi va hech qachon chop etilmaydi.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.telethon_guard import SHARED_PROD_FILES, _known_prod_values  # noqa: E402

DEFAULT_ENV_FILE = "/etc/oisha/juma.env"
SESSION_ENV_KEY = "JUMA_SESSION_STRING"
DEVICE_MODEL = "Oisha Juma Broadcast"
QR_ATTEMPTS = 10


def upsert_juma_env(
    path: Path, session_str: str, *, repo_root: Path = REPO_ROOT
) -> None:
    """JUMA_SESSION_STRING ni repodan tashqaridagi 0600 env fayliga yozadi."""
    clean = (session_str or "").strip()
    if not clean:
        raise ValueError("Session string boʻsh boʻlmasligi kerak.")
    resolved = path.resolve()
    root_resolved = repo_root.resolve()
    if resolved == root_resolved or root_resolved in resolved.parents:
        raise ValueError("Sirlar repo ichiga yozilmaydi.")
    path.parent.mkdir(parents=True, exist_ok=True)
    keep: list[str] = []
    if path.exists():
        keep = [
            ln
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.partition("=")[0].strip() != SESSION_ENV_KEY
        ]
    keep.append(f"{SESSION_ENV_KEY}={clean}")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(keep) + "\n")
    os.chmod(path, 0o600)


def assert_not_prod_session(
    session_str: str,
    env: Optional[Mapping[str, str]] = None,
    shared_files: Optional[Sequence[str]] = None,
) -> None:
    """Prod USERBOT_SESSION_STRING bilan bir xil kalit saqlanishini taqiqlaydi."""
    src_env = os.environ if env is None else env
    files = SHARED_PROD_FILES if shared_files is None else shared_files
    if session_str.strip() in _known_prod_values(src_env, files):
        raise ValueError(
            "Bu session prod USERBOT_SESSION_STRING bilan bir xil — alohida sessiya kerak."
        )


def show_qr(url: str, png: Optional[str]) -> None:
    """Terminalda ASCII QR va ixtiyoriy vaqtinchalik PNG chiqaradi."""
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    if png:
        qr.make_image().save(png)
        os.chmod(png, 0o600)
        print(f"QR PNG saqlandi: {png}")


async def qr_login(api_id: int, api_hash: str, png: Optional[str]) -> tuple[str, str]:
    """Telethon QR-login orqali alohida StringSession yaratadi."""
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(), api_id, api_hash, device_model=DEVICE_MODEL)
    await client.connect()
    try:
        qr = await client.qr_login()
        for _ in range(QR_ATTEMPTS):
            print("\nTelegram -> Sozlamalar -> Qurilmalar -> Qurilmani ulash:")
            show_qr(qr.url, png)
            try:
                timeout = max(10, int((qr.expires - datetime.now(qr.expires.tzinfo)).total_seconds()))
                await qr.wait(timeout=timeout)
                break
            except asyncio.TimeoutError:
                print("QR muddati tugadi, yangilanmoqda...")
                await qr.recreate()
            except SessionPasswordNeededError:
                await client.sign_in(password=getpass.getpass("2FA parol (koʻrinmaydi): "))
                break
        else:
            raise SystemExit("QR kod skanerlanmadi.")
        me = await client.get_me()
        return client.session.save(), f"@{me.username or me.id}"
    finally:
        if png and os.path.exists(png):
            os.remove(png)
        await client.disconnect()


def main(argv: Optional[list[str]] = None) -> None:
    """CLI orqali JUMA_SESSION_STRING yaratib 0600 env fayliga yozadi."""
    parser = argparse.ArgumentParser(description="Juma tabrigi uchun alohida QR-login")
    parser.add_argument("--env-file", default=os.getenv("JUMA_ENV_FILE", DEFAULT_ENV_FILE))
    parser.add_argument("--png", default=None, help="Vaqtinchalik QR PNG yoʻli")
    args = parser.parse_args(argv)

    api_id = int(os.getenv("API_ID", "0") or 0)
    api_hash = os.getenv("API_HASH", "").strip()
    if not api_id or not api_hash:
        raise SystemExit("API_ID va API_HASH muhitda boʻlishi kerak.")

    session_str, who = asyncio.run(qr_login(api_id, api_hash, args.png))
    assert_not_prod_session(session_str)
    env_path = Path(args.env_file)
    upsert_juma_env(env_path, session_str)
    print(f"OK: {who} uchun {SESSION_ENV_KEY} saqlandi ({env_path}, 0600).")


if __name__ == "__main__":
    main()
