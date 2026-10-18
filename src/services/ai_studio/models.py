"""
AI Studio Ingestion and Sync Models
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AppSyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"
    STANDARDS_VIOLATED = "standards_violated"


class AIStudioAppConfig(BaseModel):
    """Configuration for an AI Studio application source."""
    app_id: str = Field(..., description="Google AI Studio application UUID")
    repo_name: str = Field(
        default="baxtiyorjongaziyev/oisha-os-preview",
        description="Target GitHub repository for AI Studio export",
    )
    branch: str = Field(default="main", description="Git branch to track")
    target_dir: str = Field(
        default="apps/ai_studio_preview",
        description="Local directory inside oisha-os to house the synced code",
    )
    auto_modularize: bool = Field(
        default=True,
        description="Automatically split God-files (>400 lines) into modular subcomponents",
    )
    run_preflight: bool = Field(
        default=True,
        description="Run pytest and bandit after ingestion",
    )


class FileAuditReport(BaseModel):
    """Report for an individual source file scanned during ingestion."""
    path: str
    total_lines: int
    is_god_file: bool = False
    split_into: List[str] = Field(default_factory=list)
    syntax_valid: bool = True
    error_message: Optional[str] = None


class IngestionSummary(BaseModel):
    """Summary of an AI Studio ingestion run."""
    app_id: str
    synced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: AppSyncStatus = AppSyncStatus.IDLE
    commit_sha: Optional[str] = None
    files_processed: int = 0
    god_files_detected: int = 0
    god_files_refactored: int = 0
    file_reports: List[FileAuditReport] = Field(default_factory=list)
    preflight_passed: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
