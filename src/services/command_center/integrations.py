"""
Integration capability listings and Telegram bot migration statuses.
"""
from __future__ import annotations

from dataclasses import asdict
import os
from typing import Any, Dict, List
from src.settings import settings
from src.services.command_center.models import (
    BrandingERPPhase,
    IntegrationCapability,
    TelegramMigrationCheck,
    TelegramMigrationStatus,
    _configured,
)

def list_integration_capabilities() -> list[dict[str, Any]]:
    """Return truthful runtime capabilities without exposing secret values."""
    capabilities = [
        IntegrationCapability(
            "amocrm",
            "amoCRM",
            _configured("AMOCRM_SUBDOMAIN", "AMOCRM_CLIENT_ID", "AMOCRM_CLIENT_SECRET"),
            ("lead_create", "task_create", "pipeline_read", "note_write"),
        ),
        IntegrationCapability(
            "telegram_bot",
            "Telegram Bot API",
            _configured("BOT_TOKEN"),
            ("notification_send", "approval_request", "command_receive"),
        ),
        IntegrationCapability(
            "telegram_userbot",
            "Telegram userbot (Oracle only)",
            os.getenv("USERBOT_RUNTIME_OWNER", "").strip().lower() == "oracle_vm"
            and _configured("USERBOT_SESSION_STRING"),
            ("conversation_read", "voice_receive"),
        ),
        IntegrationCapability(
            "airtable",
            "Airtable",
            _configured("AIRTABLE_API_KEY"),
            ("project_read", "project_update"),
        ),
        IntegrationCapability(
            "google_workspace",
            "Google Workspace",
            _configured("GOOGLE_SERVICE_ACCOUNT_JSON")
            or _configured("GOOGLE_APPLICATION_CREDENTIALS"),
            ("sheets_read", "drive_write", "calendar_event"),
        ),
    ]
    return [asdict(item) for item in capabilities]


def branding_erp_roadmap() -> list[dict[str, Any]]:
    """Return the practical integration-first ERP roadmap for branding agencies."""
    phases = [
        BrandingERPPhase(
            phase=1,
            title="24/7 runtime and truthful sources",
            outcome="Oracle VM runs the userbot, bot head, API, schedulers, and health checks without local dependency.",
            source_of_truth=("Oracle VM", "GitHub Secrets", "production .env"),
            must_run_24_7=("Telethon userbot", "bot-token head", "FastAPI health/ready", "n8n workflows"),
            acceptance_checks=("systemd active", "/healthz 200", "/readyz 200", "no local userbot session owner"),
        ),
        BrandingERPPhase(
            phase=2,
            title="Sales and follow-up control",
            outcome="AmoCRM owns lead/contact/deal/task state; Oisha only plans, verifies, and requests approval for mutations.",
            source_of_truth=("AmoCRM", "Telegram evidence"),
            must_run_24_7=("AmoCRM webhook", "sales priority digest", "follow-up reminders"),
            acceptance_checks=("pipeline IDs verified", "tasks created after approval", "stale leads routed to reactivation"),
        ),
        BrandingERPPhase(
            phase=3,
            title="Delivery and documents",
            outcome="Brief, KP, brandbook files, client feedback, project status, and deadlines are connected through cheap external tools.",
            source_of_truth=("Google Drive", "Google Sheets or Airtable", "Calendar"),
            must_run_24_7=("deadline monitor", "feedback intake", "project risk alerts"),
            acceptance_checks=("project has owner", "deadline exists", "client files linked", "risk alert has source link"),
        ),
        BrandingERPPhase(
            phase=4,
            title="Finance and margin",
            outcome="Advance, remaining payment, costs, margin, and debt are visible per client and project.",
            source_of_truth=("Hisobchi", "Google Sheets", "AmoCRM deal value"),
            must_run_24_7=("payment reminder", "margin report", "debt alert"),
            acceptance_checks=("advance verified", "expense source exists", "margin is not guessed"),
        ),
        BrandingERPPhase(
            phase=5,
            title="Aiogram bot head migration",
            outcome="Userbot stays Telethon; @jonairobot bot-account flows move to Aiogram through a compatibility adapter.",
            source_of_truth=("Telegram Bot API", "owner approval log"),
            must_run_24_7=("Aiogram dispatcher", "approval callbacks", "admin commands"),
            acceptance_checks=("Telethon userbot still authorized", "callback tests pass", "rollback to Telethon bot head is possible"),
        ),
    ]
    return [phase.to_payload() for phase in phases]


def telegram_bot_migration_status(
    *,
    bot_runtime_backend: str | None = None,
    aiogram_dispatcher_enabled: bool | None = None,
) -> dict[str, Any]:
    """Report the safe migration state without exposing Telegram secrets."""
    backend = (bot_runtime_backend or os.getenv("TELEGRAM_BOT_RUNTIME_BACKEND") or "telethon").strip().lower()
    dispatcher_enabled = (
        _env_bool("TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED")
        if aiogram_dispatcher_enabled is None
        else aiogram_dispatcher_enabled
    )
    userbot_owner = (os.getenv("USERBOT_RUNTIME_OWNER") or "").strip().lower()
    userbot_configured = _configured("USERBOT_SESSION_STRING")
    bot_token_configured = _configured("BOT_TOKEN")

    checks = (
        TelegramMigrationCheck(
            "userbot_oracle_owned",
            userbot_owner == "oracle_vm" and userbot_configured,
            "Telethon userbot must stay on Oracle VM only.",
        ),
        TelegramMigrationCheck(
            "bot_token_configured",
            bot_token_configured,
            "Bot-account token exists for outbound/admin flows.",
        ),
        TelegramMigrationCheck(
            "adapter_backend_valid",
            backend in {"telethon", "aiogram"},
            "Bot runtime backend is rollbackable between telethon and aiogram.",
        ),
        TelegramMigrationCheck(
            "aiogram_dispatcher_safe",
            not dispatcher_enabled or backend == "aiogram",
            "Aiogram dispatcher should be enabled only after backend is aiogram.",
        ),
    )

    if backend == "aiogram" and dispatcher_enabled:
        stage = "aiogram_manual_dispatcher_ready"
    elif backend == "aiogram":
        stage = "aiogram_send_only"
    else:
        stage = "telethon_adapter_ready"

    next_actions = (
        "Keep userbot on Telethon and Oracle VM.",
        "Switch TELEGRAM_BOT_RUNTIME_BACKEND=aiogram only after focused tests pass.",
        "Enable TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED only for controlled dispatcher rollout.",
        "Verify callback/update handling before full bot-account cutover.",
    )
    status = TelegramMigrationStatus(
        stage=stage,
        userbot_runtime="telethon_oracle_only" if userbot_owner == "oracle_vm" else "not_confirmed",
        bot_runtime_backend=backend,
        aiogram_dispatcher_enabled=dispatcher_enabled,
        rollback_backend="telethon",
        checks=checks,
        next_actions=next_actions,
    )
    return status.to_payload()
