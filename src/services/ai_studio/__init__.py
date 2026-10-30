"""
AI Studio Integration & Antigravity Bridge Package Facade.
"""
from __future__ import annotations

from src.services.ai_studio.models import (
    AIStudioAppConfig,
    AppSyncStatus,
    FileAuditReport,
    IngestionSummary,
)
from src.services.ai_studio.modularizer import CodeModularizer
from src.services.ai_studio.git_sync import GitSyncManager
from src.services.ai_studio.pipeline import AIStudioBridgePipeline

__all__ = [
    "AIStudioAppConfig",
    "AppSyncStatus",
    "FileAuditReport",
    "IngestionSummary",
    "CodeModularizer",
    "GitSyncManager",
    "AIStudioBridgePipeline",
]
