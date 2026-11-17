import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

from src.handlers.team_dm_reply import build_team_dm_filter


def _msg(text, uid=5, chat="private", bot=False):
    return NS(text=text, caption=None, chat=NS(type=chat), from_user=NS(id=uid, is_bot=bot))


def _run(f, m):
    return asyncio.run(f(m))


def test_team_member_dm_matches():
    f = build_team_dm_filter(lambda uid: False)
    with patch("src.services.core.daily_priority.team.find_member", return_value={"key": "x"}):
        assert _run(f, _msg("salom")) is True


def test_skips_admin_command_group_nonmember():
    with patch("src.services.core.daily_priority.team.find_member", return_value={"key": "x"}):
        assert _run(build_team_dm_filter(lambda uid: True), _msg("salom")) is False
        f = build_team_dm_filter(lambda uid: False)
        assert _run(f, _msg("/start")) is False
        assert _run(f, _msg("salom", chat="group")) is False
    with patch("src.services.core.daily_priority.team.find_member", return_value=None):
        assert _run(build_team_dm_filter(lambda uid: False), _msg("salom")) is False
