"""Merge boʻlgan PR branchiga keyin push qilingan commitlarni yoʻqotmaslik.

Muammo (2026-11-19, PR #1099): PR merge qilingan paytda agent shu branchga yana commit
push qildi; commit hech qachon ``main`` ga tushmadi. Bu skript ``push`` workflowidan
chaqiriladi va:

1. branchning merge boʻlgan PR i bormi va ochiq PR yoʻqmi — tekshiradi;
2. merge paytidagi PR head idan keyin qoʻshilgan commitlarni topadi (``<headRefOid>..HEAD``;
   repo squash-merge qilgani uchun ``git cherry`` notoʻgʻri natija beradi);
3. ``main`` dan ``followup/<branch>-<sha>`` ochib, ularni cherry-pick qiladi va PR ochadi;
4. konflikt boʻlsa — eski PR ga izoh qoldiradi (qoʻlda hal qilish kerak).

Ishlatish: ``python scripts/followup_pr.py <branch>`` (``gh`` va ``git`` kerak).
``--dry-run`` hech narsa yozmaydi, faqat rejani chiqaradi.
"""
from __future__ import annotations

import json
# Faqat git/gh, argumentlar roʻyxat koʻrinishida (shell yoʻq).
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from typing import Callable, Optional

Run = Callable[[list[str]], str]


_ALLOWED = frozenset({"git", "gh"})


def _run(cmd: list[str]) -> str:
    if not cmd or cmd[0] not in _ALLOWED:
        raise ValueError("only git/gh commands are allowed")
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout  # nosec B603 # nosemgrep


@dataclass
class Plan:
    action: str  # skip | open_pr | manual
    reason: str
    merged_pr: Optional[int] = None
    commits: tuple[str, ...] = ()
    new_branch: str = ""


def merges_after(run: Run, merged_head: str) -> list[str]:
    out = run(["git", "rev-list", "--merges", f"{merged_head}..HEAD", "^origin/main"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def pending_commits(run: Run, merged_head: str) -> list[str]:
    """Merge qilingan head dan keyingi, ``main`` da hali yoʻq commitlar (eskidan yangiga).

    ``^origin/main`` — branchga sinxronlangan main commitlari chiqarib tashlanadi;
    ``git cherry`` dagi ``-`` — oldingi follow-up orqali allaqachon tiklangan patchlar.
    """
    out = run(["git", "rev-list", "--reverse", "--no-merges", f"{merged_head}..HEAD", "^origin/main"])
    candidates = [line.strip() for line in out.splitlines() if line.strip()]
    applied = {line[2:].strip() for line in run(["git", "cherry", "origin/main", "HEAD"]).splitlines()
               if line.startswith("- ")}
    return [c for c in candidates if c not in applied]


def plan(branch: str, run: Run = _run) -> Plan:
    if branch in ("main", "master") or branch.startswith(("followup/", "dependabot/")):
        return Plan("skip", f"protected or generated branch: {branch}")
    prs = json.loads(run(["gh", "pr", "list", "--head", branch, "--state", "all",
                          "--json", "number,state,mergedAt,headRefOid", "--limit", "20"]) or "[]")
    if any(p["state"] == "OPEN" for p in prs):
        return Plan("skip", "branch already has an open PR")
    followups = json.loads(run(["gh", "pr", "list", "--state", "open", "--search", f"head:followup/{branch}-",
                                "--json", "number"]) or "[]")
    if followups:
        return Plan("skip", f"follow-up PR #{followups[0]['number']} is still open")
    merged = sorted((p for p in prs if p["state"] == "MERGED"), key=lambda p: p["mergedAt"] or "")
    if not merged:
        return Plan("skip", "branch has no merged PR")
    last = merged[-1]
    if not last.get("headRefOid"):
        return Plan("skip", "merged PR has no head sha", last["number"])
    if merges_after(run, last["headRefOid"]):
        return Plan("manual", "merge commits after the merged head: recover by hand", last["number"])
    commits = pending_commits(run, last["headRefOid"])
    if not commits:
        return Plan("skip", "everything on the branch is already in main", last["number"])
    return Plan("open_pr", f"{len(commits)} commit(s) pushed after PR #{merged[-1]['number']} merged",
                merged[-1]["number"], tuple(commits), f"followup/{branch}-{commits[-1][:7]}")


def body(p: Plan, branch: str) -> str:
    lines = "\n".join(f"- `{c[:8]}`" for c in p.commits)
    return (f"## Nimalar oʻzgardi?\n\n`{branch}` branchiga PR #{p.merged_pr} merge boʻlgandan **keyin** push "
            f"qilingan commitlar `main` ga tushmagan edi. Ular avtomatik koʻchirildi:\n\n{lines}\n\n"
            "## Nega kerak?\n\nKeyin push qilingan ish yoʻqolmasligi uchun (`scripts/followup_pr.py`).\n\n"
            "## Tekshiruv\n\n- [ ] CI yashil\n- [ ] Commitlar shu PR da kutilgan ish ekanini koʻrib chiqing\n\n"
            "## Risklar\n\nCherry-pick konfliktsiz oʻtdi; mantiqiy toʻqnashuvni review aniqlaydi.\n\n"
            "## Rollback\n\nPR ni yopish yetarli.\n")


def execute(p: Plan, branch: str, run: Run = _run) -> str:
    run(["git", "switch", "-c", p.new_branch, "origin/main"])
    try:
        run(["git", "cherry-pick", "-x", *p.commits])
    except subprocess.CalledProcessError:
        run(["git", "cherry-pick", "--abort"])
        run(["gh", "pr", "comment", str(p.merged_pr), "--body",
             f"⚠️ `{branch}` ga merge dan keyin push qilingan {len(p.commits)} ta commit `main` ga "
             "konfliktsiz koʻchmadi. Qoʻlda `main` dan yangi branch ochib PR qiling."])
        return "conflict"
    run(["git", "push", "-u", "origin", p.new_branch])
    return run(["gh", "pr", "create", "--base", "main", "--head", p.new_branch,
                "--title", f"followup: {branch} (PR #{p.merged_pr} dan keyingi commitlar)",
                "--body", body(p, branch)]).strip()


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: followup_pr.py <branch> [--dry-run]")
        return 2
    branch, dry = argv[0], "--dry-run" in argv
    p = plan(branch)
    print(f"[followup] {p.action}: {p.reason}")
    if p.action == "open_pr" and not dry:
        print(f"[followup] {execute(p, branch)}")
    elif p.action == "manual" and not dry:
        _run(["gh", "pr", "comment", str(p.merged_pr), "--body",
              f"⚠️ `{branch}` ga merge dan keyin merge-commit lar tushdi; avtomatik koʻchirish xavfli. "
              "Qoʻlda `main` dan yangi branch ochib PR qiling."])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
