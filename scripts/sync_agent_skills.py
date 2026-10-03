"""Mirror .claude/skills into .agents/skills for Codex, Antigravity and Cursor.

Claude Code reads only .claude/skills; Codex and Antigravity read .agents/skills.
Real copies instead of symlinks: git on Windows checks symlinks out as text files.
Git stores identical blobs once, so the mirror adds no repository size.

    python scripts/sync_agent_skills.py          # update the mirror
    python scripts/sync_agent_skills.py --check  # exit 1 if the mirror drifted
"""
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".claude" / "skills"
DST = ROOT / ".agents" / "skills"


def _files(base: Path) -> set[str]:
    if not base.exists():
        return set()
    return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


def drift() -> list[str]:
    """Paths that are missing, extra, or different in the mirror."""
    src, dst = _files(SRC), _files(DST)
    changed = {f for f in src & dst if not filecmp.cmp(SRC / f, DST / f, shallow=False)}
    return sorted((src ^ dst) | changed)


def main() -> int:
    stale = drift()
    if "--check" in sys.argv:
        for path in stale:
            print(f"out of sync: {path}")
        if stale:
            print("Run: python scripts/sync_agent_skills.py")
        return 1 if stale else 0
    if stale:
        shutil.rmtree(DST, ignore_errors=True)
        shutil.copytree(SRC, DST)
    print(f"{len(stale)} path(s) synced to {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
