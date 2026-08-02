"""Cloud Run entrypoint for Oisha's isolated @jonairobot head.

Only the Bot API token head is composed here.  Telethon, API_ID/API_HASH and
USERBOT_SESSION_STRING are intentionally outside this process.
"""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request

from src.db import Database
from src.services.core.admin_aiogram_dispatcher import (
    build_admin_aiogram_dispatcher,
    register_hisobchi_aiogram_callbacks,
)
from src.services.core.finance.hisobchi_schema import create_hisobchi_engine
from src.services.core.telegram.aiogram_webhook_head import (
    AiogramWebhookHead,
    DatabaseUpdateReceiptStore,
)
from src.services.utils.access_manager import AccessManager
from src.settings import settings

WEBHOOK_PATH = "/telegram/webhook"


@dataclass
class AiogramCloudRuntime:
    head: AiogramWebhookHead
    database: Any


RuntimeFactory = Callable[[], Awaitable[AiogramCloudRuntime]]


def _secret_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if getter else value).strip()


async def build_runtime() -> AiogramCloudRuntime:
    """Compose the cloud head from shared Oisha adapters."""
    from aiogram import Bot

    bot_token = _secret_text(settings.BOT_TOKEN)
    webhook_secret = _secret_text(settings.TELEGRAM_WEBHOOK_SECRET)
    base_url = str(settings.AIOGRAM_WEBHOOK_BASE_URL or "").strip().rstrip("/")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required for the Aiogram cloud head")
    if not webhook_secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is required")
    if base_url and not base_url.startswith("https://"):
        raise RuntimeError("AIOGRAM_WEBHOOK_BASE_URL must be a public HTTPS URL")
    if not settings.TURSO_DATABASE_URL or not _secret_text(settings.TURSO_AUTH_TOKEN):
        raise RuntimeError("Shared TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are required")

    database = Database(settings.DATABASE_URL)
    await database.init_instance()
    access = AccessManager(owner_id=settings.OWNER_ID)
    dispatcher = build_admin_aiogram_dispatcher(
        owner_id=access.owner_id,
        get_role=access.get_role,
        get_role_name=access.get_role_name,
        is_admin=access.is_admin,
        get_today_stats=database.get_today_stats,
        cached_crm_audit={},
        db=database,
    )
    hisobchi_engine = create_hisobchi_engine(db=database, gs_store=None)
    register_hisobchi_aiogram_callbacks(dispatcher, engine=hisobchi_engine)
    bot = Bot(token=bot_token)
    head = AiogramWebhookHead(
        bot=bot,
        dispatcher=dispatcher,
        receipt_store=DatabaseUpdateReceiptStore(database),
        webhook_url=f"{base_url}{WEBHOOK_PATH}" if base_url else "",
        webhook_secret=webhook_secret,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
    return AiogramCloudRuntime(head=head, database=database)


def create_app(*, runtime_factory: RuntimeFactory = build_runtime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = await runtime_factory()
        app.state.runtime = runtime
        await runtime.head.start()
        try:
            yield
        finally:
            await runtime.head.stop()
            close = getattr(runtime.database, "close", None)
            if close is not None:
                await close()

    app = FastAPI(title="Oisha Aiogram Cloud Head", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, Any]:
        runtime = getattr(request.app.state, "runtime", None)
        if runtime is None:
            return {
                "status": "starting",
                "head": "aiogram_bot_token",
                "userbot_enabled": False,
            }
        return runtime.head.health()

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> dict[str, Any]:
        expected = _secret_text(settings.TELEGRAM_WEBHOOK_SECRET)
        received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not expected:
            raise HTTPException(status_code=503, detail="Webhook secret unavailable")
        if not hmac.compare_digest(expected, received):
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid Telegram update payload")
        try:
            return await request.app.state.runtime.head.receive(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
