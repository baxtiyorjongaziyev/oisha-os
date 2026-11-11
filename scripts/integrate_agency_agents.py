#!/usr/bin/env python3
"""
Integrate the `agency-agents` submodule into the Oisha‑OS workspace.

The mapping table determines where each top‑level folder from the submodule
should live in the main project. Adjust `FOLDER_MAP` if you need a different
placement.

Author: Antigravity (automated)
"""

import os
import shutil
import subprocess
from pathlib import Path

# ----------------------------------------------------------------------
# 1️⃣ Mapping of source → destination
# ----------------------------------------------------------------------
# Keys are top‑level directories inside `agency-agents/`.
# Values are relative paths inside the main workspace where the content should go.
FOLDER_MAP = {
    "academic":        "docs/agency/academic",
    "design":          "design",
    "engineering":     "src/engineering",
    "examples":        "examples",
    "finance":         "finance",
    "game-development":"games",
    "gis":             "gis",
    "healthcare":      "healthcare",
    "integrations":    "integrations",
    "marketing":       "marketing-os",          # existing marketing module
    "paid-media":      "marketing-os/paid-media",
    "product":         "product",
    "project-management":"project-management",
    "research":        "research",
    "sales":           "salescoach-ai",         # existing salescoach module
    "scripts":         "scripts/agency-agents",
    "security":        "security",
    "spatial-computing":"spatial-computing",
    "specialized":     "specialized",
    "strategy":        "strategy",
    "support":         "support",
    "testing":         "tests/agency-agents",
    # Anything not listed will be copied into `misc/agency-agents`
}

# ----------------------------------------------------------------------
# 2️⃣ Helper utilities
# ----------------------------------------------------------------------
def copy_tree(src: Path, dst: Path):
    """Recursively copy src → dst, creating dst if needed."""
    if not src.is_dir():
        raise ValueError(f"Source {src} is not a directory")
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            copy_tree(item, target)
        else:
            shutil.copy2(item, target)

def run_git(args):
    """Run a git command in the workspace root."""
    subprocess.run(["git"] + args, check=True)

# ----------------------------------------------------------------------
# 3️⃣ Main integration logic
# ----------------------------------------------------------------------
def main():
    repo_root = Path.cwd()
    submod_root = repo_root / "agency-agents"

    if not submod_root.is_dir():
        raise RuntimeError("Submodule directory not found: agency-agents")

    # 1️⃣ Walk each top‑level folder in the submodule
    for entry in submod_root.iterdir():
        if not entry.is_dir():
            # Top‑level files like README.md, LICENSE, etc.
            dest = repo_root / entry.name
            if not dest.exists():
                shutil.copy2(entry, dest)
            continue

        src_name = entry.name
        dest_rel = FOLDER_MAP.get(src_name, f"misc/agency-agents/{src_name}")
        dest_path = repo_root / dest_rel

        print(f"Copying {src_name!r} → {dest_rel!r}")
        copy_tree(entry, dest_path)

    # 2️⃣ Update .gitignore to ignore the submodule folder (now that we copied it)
    gitignore_path = repo_root / ".gitignore"
    ignore_line = "agency-agents/\n"
    if ignore_line not in gitignore_path.read_text(encoding="utf-8"):
        with gitignore_path.open("a", encoding="utf-8") as f:
            f.write("\n# Ignore the raw submodule after integration\n")
            f.write(ignore_line)

    # 3️⃣ Commit the new files
    run_git(["add", "."])
    commit_msg = "Integrate agency‑agents collection (auto‑generated script)"
    run_git(["commit", "-m", commit_msg])

    print("\n✅ Integration completed and committed.")
    print("Review the changes (`git status` / `git diff HEAD~1`) before pushing.")

if __name__ == "__main__":
    main()
