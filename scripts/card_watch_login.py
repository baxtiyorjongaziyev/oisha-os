"""QR-code Telegram login for a sales manager's card-watch session.

Run ON THE SERVER (Hetzner), interactively, with the manager next to the screen:

    python scripts/card_watch_login.py --manager shahnoza [--png /tmp/qr.png]

The manager scans the QR in Telegram: Settings -> Devices -> Link Desktop Device.
An expired QR is replaced automatically. If 2FA is on, the manager types the
password via getpass (never logged, never stored). The device shows up in the
manager's Devices list as "Oisha Sales Monitor", where they can terminate it.

The session is encrypted immediately (Fernet, ``CARD_WATCH_SESSION_KEY``), bound
to the manager key, and written ONLY to the secrets env file (default
``/etc/oisha/card_watch.env``, mode 0600). It is never printed.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.services.core.card_watch import vault  # noqa: E402
from src.services.core.card_watch.scanner import DEVICE_MODEL, forbidden_sessions  # noqa: E402

DEFAULT_ENV_FILE = "/etc/oisha/card_watch.env"
DEFAULT_KEY_FILE = "/etc/oisha/card_watch_key.env"  # kept apart from the encrypted sessions
QR_ATTEMPTS = 10


def read_env(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def upsert_env(path: Path, updates: dict) -> None:
    """Write KEY=VALUE pairs into a 0600 file outside the repository."""
    if REPO_ROOT == path.resolve() or REPO_ROOT in path.resolve().parents:
        raise SystemExit("Refusing to write secrets inside the repository.")
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = []
    if path.exists():
        keep = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.partition("=")[0].strip() not in updates]
    keep += [f"{k}={v}" for k, v in updates.items()]
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(keep) + "\n")
    os.chmod(path, 0o600)


def show_qr(url: str, png: str | None) -> None:
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    if png:
        qr.make_image().save(png)
        os.chmod(png, 0o600)
        print(f"PNG: {png}")


async def qr_login(api_id: int, api_hash: str, png: str | None) -> tuple[str, str]:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(), api_id, api_hash, device_model=DEVICE_MODEL)
    await client.connect()
    try:
        qr = await client.qr_login()
        for _ in range(QR_ATTEMPTS):
            print("\nTelegram -> Sozlamalar -> Qurilmalar -> Link Desktop Device, QR ni skanerlang:")
            show_qr(qr.url, png)
            try:
                await qr.wait(timeout=max(10, int((qr.expires - _now(qr)).total_seconds())))
                break
            except asyncio.TimeoutError:
                print("QR muddati tugadi, yangisi chiqarilmoqda...")
                await qr.recreate()
            except SessionPasswordNeededError:
                await client.sign_in(password=getpass.getpass("2FA parol (koʻrinmaydi): "))
                break
        else:
            raise SystemExit("QR skanerlanmadi.")
        me = await client.get_me()
        return client.session.save(), f"@{me.username or me.id}"
    finally:
        if png and os.path.exists(png):
            os.remove(png)
        await client.disconnect()


def _now(qr):
    from datetime import datetime

    return datetime.now(qr.expires.tzinfo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manager", required=True, help="manager key, e.g. shahnoza")
    parser.add_argument("--env-file", default=os.getenv("CARD_WATCH_ENV_FILE", DEFAULT_ENV_FILE))
    parser.add_argument("--key-file", default=os.getenv("CARD_WATCH_KEY_FILE", DEFAULT_KEY_FILE))
    parser.add_argument("--png", default=None, help="also save QR as PNG (deleted after login)")
    args = parser.parse_args()

    api_id = int(os.getenv("API_ID", "0") or 0)
    api_hash = os.getenv("API_HASH", "")
    if not api_id or not api_hash:
        raise SystemExit("API_ID / API_HASH must be exported in the environment.")
    env_path = Path(args.env_file)
    env = read_env(env_path)
    key_path = Path(args.key_file)
    key = read_env(key_path).get(vault.KEY_ENV) or os.getenv(vault.KEY_ENV, "")
    updates = {}
    if not key:
        key = vault.new_key()
        upsert_env(key_path, {vault.KEY_ENV: key})

    manager = args.manager.strip().lower()
    session_str, who = asyncio.run(qr_login(api_id, api_hash, args.png))
    if session_str in forbidden_sessions():
        raise SystemExit("Session equals a prod session; aborting.")
    for other, stored in env.items():
        if other.startswith("CARD_WATCH_SESSION_") and other != f"CARD_WATCH_SESSION_{manager.upper()}" \
                and stored.startswith(vault.PREFIX):
            mk = other[len("CARD_WATCH_SESSION_"):].lower()
            try:
                if vault.decrypt(mk, stored, key) == session_str:
                    raise SystemExit(f"Session already used by {mk}; aborting.")
            except vault.SessionVaultError:
                continue
    updates[f"CARD_WATCH_SESSION_{manager.upper()}"] = vault.encrypt(manager, session_str, key)
    upsert_env(env_path, updates)
    print(f"OK: {who} -> {manager} shifrlab saqlandi ({env_path}, 0600). Endi: sudo systemctl restart oisha")


if __name__ == "__main__":
    main()
