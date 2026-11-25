"""Unit tests for scripts/ai_pr_bug_review.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts import ai_pr_bug_review as mod


def test_filter_diff_drops_lockfiles_and_keeps_code() -> None:
    raw = (
        "diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml\n"
        "+huge lockfile line\n"
        "diff --git a/src/app.py b/src/app.py\n"
        "+def hello():\n+    return 1\n"
    )
    filtered = mod.filter_diff(raw)
    assert "pnpm-lock.yaml" not in filtered
    assert "src/app.py" in filtered
    assert "def hello():" in filtered


def test_filter_diff_truncates_large_diff() -> None:
    raw = "diff --git a/src/big.py b/src/big.py\n" + ("x" * 200)
    filtered = mod.filter_diff(raw, max_chars=80)
    assert "diff truncated at 80 chars" in filtered


def test_main_skips_when_api_key_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_REVIEW_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    diff_file = tmp_path / "pr.diff"
    out_file = tmp_path / "review.md"
    diff_file.write_text("diff --git a/a.py b/a.py\n+x = 1\n", encoding="utf-8")

    code = mod.main(["--diff-file", str(diff_file), "--output-file", str(out_file)])
    assert code == 0
    assert not out_file.exists()


def test_main_writes_formatted_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_REVIEW_API_KEY", "test-key")
    diff_file = tmp_path / "pr.diff"
    out_file = tmp_path / "review.md"
    diff_file.write_text("diff --git a/a.py b/a.py\n+x = 1 / 0\n", encoding="utf-8")

    with patch.object(mod, "call_gemini", return_value="- HIGH: ZeroDivisionError") as mock_call:
        code = mod.main(["--diff-file", str(diff_file), "--output-file", str(out_file)])

    assert code == 0
    mock_call.assert_called_once()
    content = out_file.read_text(encoding="utf-8")
    assert mod.MARKER in content
    assert "ZeroDivisionError" in content
