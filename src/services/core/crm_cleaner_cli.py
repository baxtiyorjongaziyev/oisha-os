"""CRM Cleaner CLI.

Bu skript ikkita yangi modulni xavfsiz tarzda ishga tushiradi:

  1) telegram_phone_enricher — AmoCRM contactlaridagi yo'q telefon raqamlarini
     Telegram orqali topib, CRM ga yozadi. AmoCRM ning native auto-deduplicate
     funksiyasi keyin avtomatik birlashtiradi.
  2) deal_ai_analyzer — har bir aktiv sdelkani Gemini/Claude yordamida
     tahlil qilib, kategoriya tegi va izoh qoldiradi.

Foydalanish:
    # Faqat hisobot (dry-run, hech narsa yozilmaydi)
    python -m src.services.core.crm_cleaner_cli --mode enrich --limit 100

    # AmoCRM ga yozib qo'yish
    python -m src.services.core.crm_cleaner_cli --mode enrich --limit 100 --apply

    # Sdelkalarni AI bilan tahlil qilish va teg qo'yish
    python -m src.services.core.crm_cleaner_cli --mode analyze --limit 50 --apply

    # Hammasini birga
    python -m src.services.core.crm_cleaner_cli --mode all --limit 100 --apply

Xavfsizlik:
- `--apply` bo'lmasa hech narsa yozilmaydi (default = dry-run).
- Quiet-hours `agent_policy` orqali tekshiriladi (`--force` bilan bekor qilinadi).
- Har bir run JSON hisobotni `reports/crm_cleaner_<ts>.json` ga yozadi.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("crm_cleaner")


# -------- AI provider plumbing ----------

async def _gemini_call(prompt: str) -> str:
    import google.generativeai as genai  # type: ignore
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable yo'q")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        os.getenv("GEMINI_CALL_MODEL", "gemini-2.5-flash")
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    return getattr(response, "text", "") or ""


async def _claude_call(prompt: str) -> str:
    import anthropic  # type: ignore
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable yo'q")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in getattr(msg, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts).strip()


def _select_ai_call(name: str) -> Callable[[str], Awaitable[str]]:
    name = (name or "gemini").lower()
    if name == "claude":
        return _claude_call
    if name == "gemini":
        return _gemini_call
    raise ValueError(f"Noma'lum AI provayder: {name}")


# -------- Telegram client ----------

async def _connect_telegram():
    from telethon import TelegramClient  # type: ignore
    from telethon.sessions import StringSession  # type: ignore

    api_id = int(os.getenv("API_ID", "0") or 0)
    api_hash = os.getenv("API_HASH", "")
    session_string = os.getenv("TELEGRAM_SESSION_STRING", "")
    session_file = os.getenv("TELEGRAM_SESSION_FILE", "data/userbot_session.session")

    if not api_id or not api_hash:
        raise RuntimeError("API_ID va API_HASH .env ga qo'shilishi kerak")

    if session_string:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
    else:
        client = TelegramClient(session_file, api_id, api_hash)

    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram userbot session avtorizatsiya qilinmagan. "
            "Avval `python -m src.auth_step1` ni ishga tushiring."
        )
    me = await client.get_me()
    logger.info(f"[CLI] Telegram ulandi: @{getattr(me, 'username', '')} ({getattr(me, 'id', '')})")
    return client


# -------- AmoCRM client ----------

def _build_amocrm():
    from src.services.core.amocrm_sync import AmoCRMSync
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "")
    client_id = os.getenv("AMOCRM_CLIENT_ID", "")
    client_secret = os.getenv("AMOCRM_CLIENT_SECRET", "")
    redirect = os.getenv("AMOCRM_REDIRECT_URL", "https://oisha.local/oauth")
    token_file = os.getenv("AMOCRM_TOKEN_FILE", "data/amocrm_token.json")
    if not subdomain or not client_id:
        raise RuntimeError("AMOCRM_SUBDOMAIN va AMOCRM_CLIENT_ID kerak")
    return AmoCRMSync(
        subdomain=subdomain,
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=redirect,
        token_file=token_file,
    )


# -------- Quiet hours guard ----------

def _quiet_hours_blocked(force: bool) -> bool:
    if force:
        return False
    try:
        from src.services.core.agent_policy import is_quiet_hours  # type: ignore
        return bool(is_quiet_hours())
    except Exception:
        return False


# -------- Runners ----------

async def _run_enrich(args, amocrm, tg_client) -> dict:
    from src.services.core.telegram_phone_enricher import (
        TelegramPhoneEnricher,
        report_to_dict,
    )
    enricher = TelegramPhoneEnricher(amocrm=amocrm, tg_client=tg_client)
    report = await enricher.run(limit=args.limit, dry_run=not args.apply)
    return report_to_dict(report)


async def _run_analyze(args, amocrm, tg_client) -> dict:
    from src.services.core.deal_ai_analyzer import (
        DealAIAnalyzer,
        report_to_dict,
    )
    ai_call = _select_ai_call(args.ai)
    analyzer = DealAIAnalyzer(
        amocrm=amocrm,
        tg_client=tg_client,
        ai_call=ai_call,
        message_window=args.messages,
    )
    report = await analyzer.run(
        limit=args.limit,
        dry_run=not args.apply,
        skip_closed=not args.include_closed,
    )
    return report_to_dict(report)


def _write_report(name: str, data: dict) -> Path:
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = out_dir / f"crm_cleaner_{name}_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _format_summary(name: str, data: dict) -> str:
    lines = [f"==== {name.upper()} ===="]
    if name == "enrich":
        lines += [
            f"Tekshirildi: {data.get('checked')}",
            f"Raqamsiz: {data.get('no_phone')}",
            f"Topildi: {data.get('resolved')}",
            f"Qo'llanildi: {data.get('applied')}",
            f"Yashirin: {data.get('hidden')}",
            f"Xatolar: {data.get('errors')}",
            f"Dry-run: {data.get('dry_run')}",
        ]
    elif name == "analyze":
        lines.append(f"Tekshirildi: {data.get('checked')}")
        lines.append(f"Dry-run: {data.get('dry_run')}")
        lines.append("Kategoriyalar bo'yicha:")
        for cat, n in (data.get("by_category") or {}).items():
            lines.append(f"  {cat}: {n}")
    return "\n".join(lines)


async def _main(args) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    if _quiet_hours_blocked(args.force):
        print("[CRM CLEANER] Sukunat soatlari. --force bilan ishga tushiring yoki kuting.")
        return 2

    amocrm = _build_amocrm()
    tg_client = None
    try:
        tg_client = await _connect_telegram()

        outputs = {}
        if args.mode in ("enrich", "all"):
            outputs["enrich"] = await _run_enrich(args, amocrm, tg_client)
            path = _write_report("enrich", outputs["enrich"])
            print(_format_summary("enrich", outputs["enrich"]))
            print(f"Hisobot: {path}")

        if args.mode in ("analyze", "all"):
            outputs["analyze"] = await _run_analyze(args, amocrm, tg_client)
            path = _write_report("analyze", outputs["analyze"])
            print(_format_summary("analyze", outputs["analyze"]))
            print(f"Hisobot: {path}")

        return 0
    finally:
        if tg_client:
            await tg_client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Oisha CRM Cleaner — enrich + analyze")
    parser.add_argument(
        "--mode",
        choices=("enrich", "analyze", "all"),
        default="enrich",
        help="enrich: telefon raqamini topish; analyze: AI bilan sdelkalarni tasniflash",
    )
    parser.add_argument("--limit", type=int, default=100, help="Tekshiriladigan obyektlar soni")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="AmoCRM ga yozib qo'yish (default = dry-run)",
    )
    parser.add_argument(
        "--ai",
        choices=("gemini", "claude"),
        default="gemini",
        help="Sdelka tahlili uchun AI provayder",
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=30,
        help="Har sdelka uchun Telegram xabar oynasi",
    )
    parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Yopilgan (won/lost) sdelkalarni ham tekshirish",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sukunat soatlarini chetlab o'tish",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_main(args))
    except KeyboardInterrupt:
        print("Bekor qilindi")
        return 130
    except Exception as exc:
        logger.exception("CRM cleaner xatoligi")
        print(f"XATO: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
