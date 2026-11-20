"""
AI Studio Git Synchronizer
Handles repository cloning, pulling, and commit inspection for AI Studio prototypes.
"""
from __future__ import annotations

import base64
import os
import subprocess  # nosec B404
from pathlib import Path
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger("AIStudioGitSync")


class GitSyncManager:
    """Manages Git synchronization between AI Studio exports and Antigravity."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent.parent.parent

    def _git_env(self, repo_url: str) -> Dict[str, str]:
        """Builds subprocess env with GitHub header auth without putting tokens in argv."""
        env = dict(os.environ)
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        token = (env.get("AI_STUDIO_GITHUB_TOKEN") or env.get("GITHUB_TOKEN") or "").strip()
        if token and repo_url.startswith("https://github.com/"):
            basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
            env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {basic}"
        return env

    def get_latest_remote_commit(self, repo_url: str, branch: str = "main") -> Optional[str]:
        """Fetches the latest commit SHA from the remote git repository using ls-remote."""
        cmd = ["git", "ls-remote", repo_url, f"refs/heads/{branch}"]
        try:
            res = subprocess.run(  # nosec B603 # nosemgrep
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
                env=self._git_env(repo_url),
            )
            output = res.stdout.strip()
            if output:
                return output.split()[0]
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            logger.warning("Failed to fetch remote commit SHA", repo_url=repo_url, error=str(exc))
        return None

    def sync_repository(
        self,
        repo_url: str,
        target_dir: Path,
        branch: str = "main",
    ) -> bool:
        """Clones or pulls the latest files from the AI Studio GitHub repository."""
        target_dir.mkdir(parents=True, exist_ok=True)
        git_dir = target_dir / ".git"

        if git_dir.exists():
            return self._pull_updates(target_dir, branch)
        return self._clone_repo(repo_url, target_dir, branch)

    def _clone_repo(self, repo_url: str, target_dir: Path, branch: str) -> bool:
        """Clones a remote repository into target_dir."""
        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            repo_url,
            str(target_dir),
        ]
        try:
            subprocess.run(  # nosec B603 # nosemgrep
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
                env=self._git_env(repo_url),
            )
            logger.info("Successfully cloned AI Studio repo", repo=repo_url, target=str(target_dir))
            return True
        except subprocess.SubprocessError as exc:
            logger.error("Git clone failed", repo=repo_url, error=str(exc))
            return False

    def _pull_updates(self, target_dir: Path, branch: str) -> bool:
        """Pulls latest updates in an already cloned directory."""
        cmd = ["git", "-C", str(target_dir), "pull", "origin", branch]
        try:
            subprocess.run(  # nosec B603 # nosemgrep
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                env=self._git_env("https://github.com/"),
            )
            logger.info("Successfully pulled latest AI Studio updates", target=str(target_dir))
            return True
        except subprocess.SubprocessError as exc:
            logger.error("Git pull failed", target=str(target_dir), error=str(exc))
            return False

    def list_source_files(self, directory: Path) -> List[Path]:
        """Lists relevant source code files (.py, .ts, .tsx, .js, .jsx) in directory."""
        extensions = {".py", ".ts", ".tsx", ".js", ".jsx"}
        ignored_dirs = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
        files: List[Path] = []

        if not directory.exists():
            return files

        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in extensions:
                rel_parts = path.relative_to(directory).parts
                if not any(part in ignored_dirs or part.startswith(".") for part in rel_parts[:-1]):
                    files.append(path)
        return files
