"""scripts/followup_pr.py: merge dan keyin push qilingan commitlar yoʻqolmasligi."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

_spec = importlib.util.spec_from_file_location("followup_pr", Path("scripts/followup_pr.py"))
fp = importlib.util.module_from_spec(_spec)
sys.modules["followup_pr"] = fp
_spec.loader.exec_module(fp)


class Fake:
    def __init__(self, prs, revs="", fail_pick=False):
        self.prs, self.revs, self.fail_pick, self.calls = prs, revs, fail_pick, []

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return json.dumps(self.prs)
        if cmd[:2] == ["git", "rev-list"]:
            assert cmd[-1] == "headsha..HEAD"
            return self.revs
        if cmd[:2] == ["git", "cherry-pick"] and cmd[2] != "--abort" and self.fail_pick:
            raise subprocess.CalledProcessError(1, cmd)
        if cmd[:3] == ["gh", "pr", "create"]:
            return "https://github.com/o/r/pull/9\n"
        return ""


MERGED = [{"number": 1099, "state": "MERGED", "mergedAt": "2026-11-18T20:49:10Z", "headRefOid": "headsha"}]


def test_skips_main_followup_and_open_pr_branches():
    assert fp.plan("main", Fake([])).action == "skip"
    assert fp.plan("followup/x-abc", Fake([])).action == "skip"
    assert fp.plan("feat/x", Fake([{"number": 1, "state": "OPEN", "mergedAt": None}])).action == "skip"
    assert fp.plan("feat/x", Fake([])).action == "skip"  # PR umuman yoʻq


def test_nothing_pending_after_merge_is_skip():
    p = fp.plan("feat/x", Fake(MERGED, revs=""))
    assert p.action == "skip" and "already in main" in p.reason


def test_orphan_commit_opens_followup_pr():
    run = Fake(MERGED, revs="97e547d3abcdef\n")
    p = fp.plan("claude/x", run)
    assert p.action == "open_pr" and p.commits == ("97e547d3abcdef",) and p.merged_pr == 1099
    assert p.new_branch == "followup/claude/x-97e547d"
    assert fp.execute(p, "claude/x", run).endswith("/pull/9")
    assert ["git", "cherry-pick", "-x", "97e547d3abcdef"] in run.calls
    create = next(c for c in run.calls if c[:3] == ["gh", "pr", "create"])
    assert "#1099" in create[create.index("--body") + 1]


def test_conflict_comments_on_merged_pr_instead():
    run = Fake(MERGED, revs="bbb222\n", fail_pick=True)
    p = fp.plan("feat/x", run)
    assert fp.execute(p, "feat/x", run) == "conflict"
    assert ["git", "cherry-pick", "--abort"] in run.calls
    assert any(c[:3] == ["gh", "pr", "comment"] and c[3] == "1099" for c in run.calls)
    assert not any(c[:2] == ["git", "push"] for c in run.calls)


def test_workflow_triggers_and_permissions():
    wf = yaml.safe_load(Path(".github/workflows/followup-pr.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    assert "main" in on["push"]["branches-ignore"] and on["pull_request"]["types"] == ["closed"]
    assert wf["permissions"] == {"contents": "write", "pull-requests": "write"}
    steps = wf["jobs"]["followup"]["steps"]
    assert any("followup_pr.py" in (s.get("run") or "") for s in steps)
