"""Unit tests for src/utils/git_sync.py token handling."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from src.utils import git_sync


class _FakeProc:
    def __init__(self, rc: int = 0, out: bytes = b"", err: bytes = b""):
        self.returncode = rc
        self._out = out
        self._err = err

    async def communicate(self):
        return self._out, self._err


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token_obj,expected",
    [
        (SecretStr("ghp_secret_str_token"), "ghp_secret_str_token"),
        ("ghp_plain_str_token", "ghp_plain_str_token"),
    ],
)
async def test_push_vault_handles_secret_and_plain_tokens(tmp_path: Path, monkeypatch, token_obj, expected):
    captured_envs = []

    async def fake_exec(*args, **kwargs):
        captured_envs.append(dict(kwargs.get("env") or {}))
        return _FakeProc(0)

    monkeypatch.setattr(git_sync.settings, "GITHUB_TOKEN", token_obj)
    monkeypatch.setattr(git_sync, "_git_bin", lambda: "/usr/bin/git")
    with patch("src.utils.git_sync.asyncio.create_subprocess_exec", side_effect=fake_exec):
        await git_sync.push_vault_to_remote(tmp_path)

    assert len(captured_envs) == 3  # add, commit, push
    env = captured_envs[-1]
    assert env["GIT_HTTPS_TOKEN"] == expected
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    expected_basic = base64.b64encode(f"x-access-token:{expected}".encode("utf-8")).decode("ascii")
    assert env["GIT_CONFIG_VALUE_0"] == f"AUTHORIZATION: basic {expected_basic}"
