"""Owner-scanned, memory-only Telegram login for one read-only TN audit."""

import argparse
import asyncio
import importlib.util
import os
from pathlib import Path
import sys


def validate_owner(user, owner_id):
    if user.id != int(owner_id):
        raise ValueError("QR must be scanned by the configured owner")


async def run_audit(client, audit_main):
    previous = os.environ.get("TN_AUDIT_SESSION_STRING")
    session = client.session.save()
    await client.disconnect()
    os.environ["TN_AUDIT_SESSION_STRING"] = session
    try:
        await audit_main()
    finally:
        if previous is None:
            os.environ.pop("TN_AUDIT_SESSION_STRING", None)
        else:
            os.environ["TN_AUDIT_SESSION_STRING"] = previous


async def login_and_audit(app, qr_path):
    import qrcode
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    sys.path.insert(0, str(app))
    from src.settings import settings

    client = TelegramClient(StringSession(), settings.API_ID, settings.API_HASH)
    await client.connect()
    try:
        qr = await client.qr_login()
        qrcode.make(qr.url).save(qr_path)
        print("QR_READY: owner scan required", flush=True)
        try:
            await qr.wait(timeout=120)
        except SessionPasswordNeededError:
            password = os.environ.get("TELEGRAM_PASSWORD") or os.environ.get("TG_PASSWORD")
            if not password:
                raise RuntimeError("Telegram two-step password required") from None
            await client.sign_in(password=password)
        validate_owner(await client.get_me(), settings.OWNER_ID)
        print("OWNER_AUTHORIZED", flush=True)
        spec = importlib.util.spec_from_file_location(
            "tn_revenue_audit", app / "scripts/prod/tn_revenue_audit.py"
        )
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        sys.argv = ["tn_revenue_audit.py", "--send"]
        await run_audit(client, audit.main)
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--qr", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    args = parser.parse_args()
    status = 1
    try:
        asyncio.run(login_and_audit(args.app, args.qr))
        status = 0
    except Exception as exc:
        # Authentication exceptions may carry sensitive values; log only their type.
        print(f"TN_AUDIT_FAILED: {type(exc).__name__}", flush=True)
    finally:
        args.status.write_text(str(status), encoding="utf-8")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
