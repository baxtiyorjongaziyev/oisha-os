"""
Shared pytest fixtures for Oisha-OS.

Most tests assume a throw-away local SQLite DB. The local .env file may set
TURSO_DATABASE_URL + TURSO_AUTH_TOKEN (often a placeholder), which would make
Database.get_connection() try to connect to Turso and fail in CI / local dev.

This conftest isolates every test from that env by forcing aiosqlite fallback.
Tests that specifically exercise Turso paths must opt in via the
`use_turso_env` fixture (to be added when needed).
"""

import os
import pytest

from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()


@pytest.fixture(autouse=True)
def _force_local_sqlite(monkeypatch):
    """Strip Turso env for every test so Database falls back to aiosqlite."""
    # Clear env (covers subprocess + re-read paths)
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    # Settings object is already instantiated on import — patch attributes too
    try:
        from src.settings import settings
        monkeypatch.setattr(settings, "TURSO_DATABASE_URL", None, raising=False)
        monkeypatch.setattr(settings, "TURSO_AUTH_TOKEN", None, raising=False)
    except Exception:
        pass
    yield


_LIVE_SECRET_KEYS = (
    "GROQ_API_KEY", "CEREBRAS_API_KEY", "SAMBANOVA_API_KEY", "TOGETHERAI_API_KEY",
    "OPENROUTER_API_KEY", "NVIDIA_NIM_API_KEY", "MISTRAL_API_KEY", "HUGGINGFACE_API_KEY",
    "CLOUDFLARE_AI_API_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    # Outbound Telegram / CRM / Meta credentials — tests must never post for real.
    "BOT_TOKEN", "ADMIN_BOT_TOKEN", "USERBOT_SESSION_STRING", "TELEGRAM_MCP_SESSION_STRING",
    "AMOCRM_ACCESS_TOKEN", "AIRTABLE_ACCESS_TOKEN", "AIRTABLE_API_KEY",
    "META_PAGE_ACCESS_TOKEN", "CMS_WEBHOOK_URL",
)


@pytest.fixture(autouse=True)
def _strip_live_credentials(monkeypatch):
    """Under SKIP_LIVE, never let tests hit real AI providers, Telegram, AmoCRM
    or Meta with credentials loaded from the local .env. Tests needing a key set it themselves."""
    if os.getenv("SKIP_LIVE") != "1":
        yield
        return
    try:
        from src.settings import settings
    except Exception:
        settings = None
    for key in _LIVE_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
        if settings is not None and hasattr(settings, key):
            current = getattr(settings, key)
            blank = SecretStr("") if isinstance(current, SecretStr) else None
            monkeypatch.setattr(settings, key, blank, raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_gemini_model_quota_cooldowns():
    """Keep process-level Gemini cooldown state isolated between tests."""
    from src.services.utils.gemini_fallback import reset_model_quota_cooldowns

    reset_model_quota_cooldowns()
    yield
    reset_model_quota_cooldowns()


@pytest.fixture(autouse=True)
def _reset_api_state_db_instance():
    """api_state.db_instance is a module-level global. Some routes
    (src/api/routes/amocrm_integration.py's _get_db_instance) lazily create a
    real Database() and assign it here as a side effect the first time
    they're hit, and any test that patches it with a bare MagicMock leaves
    that behind too — so whichever test runs next inherits either a stray
    real DB or a non-async mock instead of the None it expects, and any
    `await db_instance.something()` blows up with 'MagicMock can't be used
    in an await expression'."""
    from src.api.routes.state import api_state

    original = api_state.db_instance
    yield
    api_state.db_instance = original


@pytest.fixture(autouse=True)
def _reset_agent_runtime_context():
    """agent_runtime._runtime_context is a module-level global that leaks
    across the whole pytest session otherwise — e.g. GitHub Actions runners
    have SYSTEMD_EXEC_PID set, so the first test to resolve it pins
    runtime_source to "vm_service" for every test that runs afterward,
    regardless of what that test is actually exercising."""
    from src.services.core.agent_runtime import reset_runtime_context

    reset_runtime_context()
    yield
    reset_runtime_context()


def pytest_sessionfinish(session, exitstatus):
    """Store the pytest exit status code on the config object for unconfigure."""
    session.config._pytest_exitstatus = int(exitstatus)


def pytest_unconfigure(config):
    """Ensure pytest process exits cleanly on CI without hanging indefinitely
    on non-daemon background threads or unclosed event loop portals left behind
    by async tests (e.g. Starlette TestClient / AnyIO BlockingPortal).
    """
    import os
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("FORCE_PYTEST_EXIT") == "1":
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        code = getattr(config, "_pytest_exitstatus", 0)
        os._exit(code)

