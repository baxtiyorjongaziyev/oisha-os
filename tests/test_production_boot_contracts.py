from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_server_does_not_import_untracked_oauth_router():
    source = (ROOT / "src" / "api_server.py").read_text(encoding="utf-8")

    assert "src.api.routes.oauth2" not in source
    assert "include_router(oauth2_router)" not in source


def test_boot_keeps_local_aliases_after_context_migration():
    source = (ROOT / "src" / "boot.py").read_text(encoding="utf-8")
    assignments = (
        "msg_controller = app_ctx.msg_controller",
        "client = app_ctx.client",
        "bot_client = app_ctx.bot_client",
        "BOT_TOKEN_STR = app_ctx.bot_token_str",
        "bot_runtime = app_ctx.bot_runtime",
    )

    for assignment in assignments:
        assert assignment in source
    assert source.index("bot_runtime = app_ctx.bot_runtime") < source.index("bot_runtime.backend")


def test_source_web_service_limits_restart_storm_and_requires_build():
    unit = (ROOT / "deploy" / "oisha-web.service").read_text(encoding="utf-8")

    assert "StartLimitIntervalSec=60" in unit
    assert "StartLimitBurst=3" in unit
    assert "ExecStartPre=/usr/bin/test -f /home/ubuntu/oisha-os/salescoach-ai/apps/web/.next/BUILD_ID" in unit


def test_optional_brain_synthesizer_cannot_abort_core_boot():
    source = (ROOT / "src" / "boot.py").read_text(encoding="utf-8")

    import_line = "from src.schedulers.cloud_brain_synthesizer import brain_synthesizer_loop"
    import_pos = source.index(import_line)
    try_pos = source.rfind("try:", 0, import_pos)
    except_pos = source.index("except ImportError", import_pos)

    assert try_pos != -1
    assert try_pos < import_pos < except_pos
