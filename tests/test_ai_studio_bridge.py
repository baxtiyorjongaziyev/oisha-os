"""
Tests for AI Studio Bridge, Git Sync, and Modularizer.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.ai_studio import (
    AIStudioAppConfig,
    AIStudioBridgePipeline,
    AppSyncStatus,
    CodeModularizer,
    FileAuditReport,
    GitSyncManager,
    IngestionSummary,
)


def test_models_defaults_and_validation():
    config = AIStudioAppConfig(app_id="test-uuid-123")
    assert config.app_id == "test-uuid-123"
    assert config.branch == "main"
    assert config.auto_modularize is True

    summary = IngestionSummary(app_id="test-uuid-123")
    assert summary.status == AppSyncStatus.IDLE
    assert summary.files_processed == 0


def test_modularizer_clean_file(tmp_path: Path):
    clean_py = tmp_path / "clean_module.py"
    clean_py.write_text("x = 1\ny = 2\n", encoding="utf-8")

    mod = CodeModularizer(max_lines=400)
    report = mod.audit_file(clean_py)

    assert report.total_lines == 2
    assert report.is_god_file is False
    assert report.syntax_valid is True

    changed, files = mod.modularize_if_needed(clean_py)
    assert changed is False
    assert files == []


def test_modularizer_preserves_python_until_safe_extraction_exists(tmp_path: Path):
    god_py = tmp_path / "giant_service.py"
    lines = [f"def func_{i}():\n    return {i}\n" for i in range(250)]  # 500 lines
    god_py.write_text("\n".join(lines), encoding="utf-8")

    mod = CodeModularizer(max_lines=400)
    report = mod.audit_file(god_py)
    assert report.is_god_file is True

    original = god_py.read_bytes()
    assert mod.modularize_if_needed(god_py) == (False, [])
    assert god_py.read_bytes() == original


def test_modularizer_preserves_ts_until_safe_extraction_exists(tmp_path: Path):
    god_tsx = tmp_path / "GiantComponent.tsx"
    lines = [f"export const Item{i} = () => <div>{i}</div>;" for i in range(450)]
    god_tsx.write_text("\n".join(lines), encoding="utf-8")

    mod = CodeModularizer(max_lines=400)
    report = mod.audit_file(god_tsx)
    assert report.is_god_file is True

    original = god_tsx.read_bytes()
    assert mod.modularize_if_needed(god_tsx) == (False, [])
    assert god_tsx.read_bytes() == original


def test_git_sync_list_source_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "src" / "index.ts").write_text("console.log('hi')", encoding="utf-8")
    (tmp_path / "src" / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "node_modules" / "bad.js").write_text("// bad", encoding="utf-8")

    manager = GitSyncManager(workspace_root=tmp_path)
    files = manager.list_source_files(tmp_path)
    file_names = {f.name for f in files}

    assert "index.ts" in file_names
    assert "app.py" in file_names
    assert "bad.js" not in file_names


def test_pipeline_run_end_to_end_mocked(tmp_path: Path):
    mock_git = MagicMock(spec=GitSyncManager)
    mock_git.get_latest_remote_commit.return_value = "abc123sha"
    mock_git.sync_repository.return_value = True

    test_file = tmp_path / "sample.py"
    test_file.write_text("val = 42\n", encoding="utf-8")
    mock_git.list_source_files.return_value = [test_file]

    config = AIStudioAppConfig(
        app_id="app-456",
        repo_name="test/repo",
        target_dir="tmp_target",
        run_preflight=False,
    )

    pipeline = AIStudioBridgePipeline(workspace_root=tmp_path, git_sync=mock_git)
    summary = pipeline.run_pipeline(config)

    assert summary.status == AppSyncStatus.COMPLETED
    assert summary.commit_sha == "abc123sha"
    assert summary.files_processed == 1
    assert summary.god_files_detected == 0
