"""Audit imported code without destructive, syntax-unaware rewrites."""
from __future__ import annotations

import ast
from pathlib import Path

import structlog

from src.services.ai_studio.models import FileAuditReport

logger = structlog.get_logger("AIStudioModularizer")
MAX_ALLOWED_LINES = 400
MAX_FUNCTION_LINES = 60


class CodeModularizer:
    """Audit source; oversized files require a reviewed refactor."""

    def __init__(self, max_lines: int = MAX_ALLOWED_LINES):
        self.max_lines = max_lines

    def audit_file(self, file_path: Path) -> FileAuditReport:
        if not file_path.is_file():
            return FileAuditReport(path=str(file_path), total_lines=0,
                                   syntax_valid=False, error_message="File does not exist")
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return FileAuditReport(path=str(file_path), total_lines=0,
                                   syntax_valid=False, error_message="Source is unreadable or not UTF-8")
        total_lines = len(content.splitlines())
        report = FileAuditReport(path=str(file_path), total_lines=total_lines,
                                 is_god_file=total_lines > self.max_lines)
        if file_path.suffix == ".py":
            try:
                ast.parse(content, filename=str(file_path))
            except SyntaxError as exc:
                report.syntax_valid = False
                report.error_message = f"Syntax error at line {exc.lineno}: {exc.msg}"
        return report

    def modularize_if_needed(self, file_path: Path) -> tuple[bool, list[Path]]:
        """Preserve source until dependency-aware extraction/build checks exist."""
        if self.audit_file(file_path).is_god_file:
            logger.warning("Reviewed refactor required; source preserved", path=str(file_path))
        return False, []
