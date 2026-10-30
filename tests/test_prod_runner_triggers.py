"""Jobs on the production runner (label "oracle") must only run trusted code.

A push to any feature branch would otherwise execute that branch's code on
the prod host with prod secrets, so push triggers must be limited to main.
"""
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
TRUSTED_BRANCHES = {"main", "master", "ops/web-deploy"}


def _uses_prod_runner(doc):
    for job in (doc.get("jobs") or {}).values():
        runs_on = job.get("runs-on")
        labels = runs_on if isinstance(runs_on, list) else [runs_on]
        if "oracle" in labels:
            return True
    return False


def test_prod_runner_workflows_only_run_trusted_refs():
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not _uses_prod_runner(doc):
            continue
        triggers = doc.get(True, doc.get("on")) or {}
        if isinstance(triggers, str):
            triggers = {triggers: None}
        if "push" in triggers:
            branches = set((triggers["push"] or {}).get("branches") or [])
            if not branches or not branches <= TRUSTED_BRANCHES:
                offenders.append(f"{path.name}: push branches={sorted(branches) or 'ANY'}")
    assert not offenders, offenders
