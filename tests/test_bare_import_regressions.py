"""Live paths must not depend on modules that only import under pytest (audit 2026-11-07).

pytest.ini puts `src/` on sys.path, so `from database import Database` works in
tests but raises ModuleNotFoundError in production (main.py adds only the
project root). team_hub.py is such a module; /set_position and the workflow
loop used to import it.
"""
from __future__ import annotations

import ast
import datetime as _dt
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

def _src_root_names() -> set[str]:
    names = {p.stem for p in SRC.glob("*.py")}
    names |= {p.name for p in SRC.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    return names


def _bare_imports() -> list[str]:
    """Imports that resolve only with src/ (root names) or the file's own dir (siblings) on sys.path."""
    roots = _src_root_names()
    found = []
    for path in SRC.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        siblings = set() if path.parent == SRC else {p.stem for p in path.parent.glob("*.py")} - {path.stem}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            else:
                continue
            if any(m.split(".")[0] in roots | siblings for m in mods):
                found.append(f"{path.relative_to(SRC).as_posix()}:{node.lineno}: {ast.unparse(node)}")
    return found


def test_no_bare_src_imports():
    bad = _bare_imports()
    assert not bad, "Use `from src.<package> import ...`:\n" + "\n".join(bad)


@pytest.mark.parametrize(
    "rel_path",
    ["services/core/workflow_manager.py", "services/core/admin_bot/handlers_sync_stats.py"],
)
def test_live_modules_do_not_import_team_hub(rel_path):
    assert "services.utils.team_hub" not in (SRC / rel_path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_evening_schedule_sends_reminder(monkeypatch):
    from src.services.core import workflow_manager as wm

    class _Monday1805(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 9, 18, 5)

    monkeypatch.setattr(wm, "datetime", types.SimpleNamespace(datetime=_Monday1805))
    monkeypatch.setattr(wm.settings, "CRM_GROUP_ID", -100123, raising=False)

    manager = wm.WorkflowManager.__new__(wm.WorkflowManager)
    manager.db = MagicMock(is_job_run=AsyncMock(return_value=False), mark_job_run=AsyncMock())
    manager.client = MagicMock(send_message=AsyncMock())

    await manager.check_periodic_schedules()

    manager.client.send_message.assert_awaited_once()
    manager.db.mark_job_run.assert_awaited_once_with("evening_result_request", "2026-11-09")


@pytest.mark.asyncio
async def test_admin_dashboard_awaits_today_stats():
    from src.admin_bot import AdminBot

    bot = AdminBot.__new__(AdminBot)
    bot.db = MagicMock(get_today_stats=AsyncMock(return_value={"leads_found": 3, "messages_synced": 12}))
    event = MagicMock(respond=AsyncMock())

    await bot.send_dashboard(event)

    msg = event.respond.await_args.args[0]
    assert "`3` ta" in msg
    assert "`12` ta" in msg
    assert "98.4%" not in msg
