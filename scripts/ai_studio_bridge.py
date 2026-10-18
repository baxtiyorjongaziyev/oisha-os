"""
AI Studio to Antigravity Synchronization CLI Tool.
Usage:
  python -m scripts.ai_studio_bridge --app-id <UUID> [--repo <owner/repo>] [--branch <branch>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import structlog

from src.services.ai_studio import (
    AIStudioAppConfig,
    AIStudioBridgePipeline,
    AppSyncStatus,
    CodeModularizer,
)

logger = structlog.get_logger("AIStudioCLI")


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for AI Studio bridge."""
    parser = argparse.ArgumentParser(
        description="Synchronize and modularize Google AI Studio apps inside Antigravity."
    )
    parser.add_argument(
        "--app-id",
        type=str,
        default="80b6106f-6db5-4f9a-9b1c-7d5a60fb7827",
        help="Google AI Studio App ID",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="baxtiyorjongaziyev/oisha-os-preview",
        help="GitHub repository path (owner/repo)",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Repository branch to sync",
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default="apps/ai_studio_preview",
        help="Local directory destination for synced code",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Audit files in target-dir without re-cloning",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Wait and poll for new commit from AI Studio before syncing",
    )
    return parser.parse_args()


def audit_existing_directory(target_path: Path) -> int:
    """Runs a standalone audit on an existing target directory."""
    modularizer = CodeModularizer()
    files = list(target_path.rglob("*"))
    source_files = [
        f for f in files
        if f.is_file() and f.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}
    ]

    print(f"\nAuditing {len(source_files)} source files in {target_path}...")
    violations = 0
    for sf in source_files:
        report = modularizer.audit_file(sf)
        if report.is_god_file:
            print(f"  [!] God-file detected: {sf.name} ({report.total_lines} lines > 400)")
            violations += 1
        else:
            print(f"  [OK] {sf.name} ({report.total_lines} lines)")

    print(f"\nAudit complete: {violations} violation(s) found.")
    return 1 if violations > 0 else 0


def _poll_for_new_commit(config: AIStudioAppConfig, workspace_root: Path) -> None:
    """Blocks until a new commit appears on the remote repository."""
    import time
    from src.services.ai_studio.git_sync import GitSyncManager
    sync_mgr = GitSyncManager(workspace_root)
    repo_url = f"https://github.com/{config.repo_name}.git"
    initial_sha = sync_mgr.get_latest_remote_commit(repo_url, config.branch)
    print(f"Watching {repo_url} ({config.branch}). Initial SHA: {initial_sha or 'None'}")
    print("Waiting for new commit from AI Studio (press Ctrl+C to stop)...")
    while True:
        time.sleep(5)
        latest = sync_mgr.get_latest_remote_commit(repo_url, config.branch)
        if latest and latest != initial_sha:
            print(f"\n[NEW COMMIT DETECTED] {latest} (was {initial_sha})")
            break
        print(".", end="", flush=True)


def main() -> int:
    """Main execution point for AI Studio Bridge CLI."""
    args = parse_arguments()
    workspace_root = Path(__file__).resolve().parent.parent

    target_path = workspace_root / args.target_dir
    if args.audit_only:
        return audit_existing_directory(target_path)

    config = AIStudioAppConfig(
        app_id=args.app_id,
        repo_name=args.repo,
        branch=args.branch,
        target_dir=args.target_dir,
    )

    if args.watch:
        _poll_for_new_commit(config, workspace_root)

    print(f"=== Antigravity AI Studio Bridge ===")
    print(f"App ID:     {config.app_id}")
    print(f"Repository: https://github.com/{config.repo_name} ({config.branch})")
    print(f"Target Dir: {target_path}")
    print(f"Starting synchronization...\n")

    pipeline = AIStudioBridgePipeline(workspace_root=workspace_root)
    summary = pipeline.run_pipeline(config)

    print(f"--- Execution Result ---")
    print(f"Status:               {summary.status.value.upper()}")
    print(f"Latest Commit SHA:    {summary.commit_sha or 'N/A'}")
    print(f"Files Processed:      {summary.files_processed}")
    print(f"God-files Detected:   {summary.god_files_detected}")
    print(f"God-files Modularized:{summary.god_files_refactored}")

    if summary.status == AppSyncStatus.FAILED:
        print(f"Error: {summary.details.get('error', 'Unknown error')}")
        return 1

    print("\n[SUCCESS] AI Studio application synced and verified with Antigravity standards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
