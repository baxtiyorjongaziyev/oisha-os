"""
AI Studio Ingestion and Integration Pipeline
Orchestrates git synchronization, modularization, and preflight verification.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
import structlog

from src.services.ai_studio.models import (
    AIStudioAppConfig,
    AppSyncStatus,
    IngestionSummary,
)
from src.services.ai_studio.modularizer import CodeModularizer
from src.services.ai_studio.git_sync import GitSyncManager

logger = structlog.get_logger("AIStudioPipeline")


class AIStudioBridgePipeline:
    """End-to-end ingestion pipeline connecting Google AI Studio to Antigravity."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        git_sync: Optional[GitSyncManager] = None,
        modularizer: Optional[CodeModularizer] = None,
    ):
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent.parent.parent
        self.git_sync = git_sync or GitSyncManager(self.workspace_root)
        self.modularizer = modularizer or CodeModularizer()

    def run_pipeline(self, config: AIStudioAppConfig) -> IngestionSummary:
        """Executes the full AI Studio -> Antigravity ingestion lifecycle."""
        summary = IngestionSummary(app_id=config.app_id, status=AppSyncStatus.SYNCING)
        target_path = self.workspace_root / config.target_dir
        repo_url = f"https://github.com/{config.repo_name}.git"

        # 1. Fetch remote commit info
        latest_sha = self.git_sync.get_latest_remote_commit(repo_url, config.branch)
        summary.commit_sha = latest_sha

        # 2. Synchronize repository files
        synced = self.git_sync.sync_repository(repo_url, target_path, config.branch)
        if not synced:
            summary.status = AppSyncStatus.FAILED
            summary.details["error"] = f"Failed to sync repository from {repo_url}"
            return summary

        # 3. Scan & Audit Files
        source_files = self.git_sync.list_source_files(target_path)
        summary.files_processed = len(source_files)

        self._process_source_files(source_files, config, summary)

        # 4. Final status determination
        if any(not report.syntax_valid for report in summary.file_reports):
            summary.status = AppSyncStatus.FAILED
            summary.details["error"] = "Source syntax validation failed"
        elif summary.god_files_detected > summary.god_files_refactored:
            summary.status = AppSyncStatus.STANDARDS_VIOLATED
        elif config.run_preflight and not self._run_preflight(summary):
            summary.status = AppSyncStatus.FAILED
        else:
            summary.status = AppSyncStatus.COMPLETED

        self._save_run_summary(summary, target_path)
        return summary

    def _run_preflight(self, summary: IngestionSummary) -> bool:
        """Run repository gates with live access disabled."""
        env = dict(os.environ, SKIP_LIVE="1", ALLOW_LOCAL_RUN="0")
        commands = [
            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
            [sys.executable, "-m", "bandit", "-r", "src/", "-ll"],
        ]
        for command in commands:
            try:
                result = subprocess.run(command, cwd=self.workspace_root, env=env,
                                        capture_output=True, text=True, timeout=600)
            except (OSError, subprocess.SubprocessError):
                summary.details["error"] = f"Preflight unavailable: {command[2]}"
                return False
            if result.returncode:
                summary.details["error"] = f"Preflight failed: {command[2]} (exit {result.returncode})"
                return False
        summary.preflight_passed = True
        return True

    def _process_source_files(
        self,
        files: list[Path],
        config: AIStudioAppConfig,
        summary: IngestionSummary,
    ) -> None:
        """Audits and optionally modularizes source files."""
        for file_path in files:
            report = self.modularizer.audit_file(file_path)
            if report.is_god_file:
                summary.god_files_detected += 1
                if config.auto_modularize:
                    success, split_files = self.modularizer.modularize_if_needed(file_path)
                    if success:
                        summary.god_files_refactored += 1
                        report.split_into = [str(f.name) for f in split_files]

            summary.file_reports.append(report)

    def _save_run_summary(self, summary: IngestionSummary, target_path: Path) -> None:
        """Saves a JSON execution log in the ingested directory."""
        log_file = target_path / "antigravity_ingest_summary.json"
        try:
            data = summary.model_dump(mode="json")
            log_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write ingest summary file", error=str(exc))
