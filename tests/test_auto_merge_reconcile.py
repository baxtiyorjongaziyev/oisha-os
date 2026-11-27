"""Execute the real workflow shell against synthetic GitHub state, never GitHub."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("updates,token,pending,disable_exit,readback,expected,success", [
    ({}, "synthetic-pat", False, "0", "true", "--auto", True),
    ({}, "synthetic-pat", False, "0", "false", "--auto", False),
    ({}, "", False, "0", "true", "", False),
    ({}, "synthetic-pat", True, "0", "true", "", True),
    ({"labels": [{"name": "no-automerge"}]}, "", True, "0", "true", "--disable-auto", True),
    ({"labels": [{"name": "no-automerge"}]}, "", False, "0", "true", "", True),
    ({"labels": [{"name": "no-automerge"}]}, "", True, "1", "true", "--disable-auto", False),
    ({"labels": [{"name": "no-automerge"}]}, "", True, "0", "false", "--disable-auto", False),
    ({"isDraft": True}, "synthetic-pat", True, "0", "true", "--disable-auto", True),
    ({"isCrossRepository": True}, "synthetic-pat", False, "0", "true", "", True),
    ({"state": "CLOSED"}, "synthetic-pat", True, "0", "true", "", True),
])
def test_reconcile_live_state(tmp_path, updates, token, pending, disable_exit, readback, expected, success):
    bash = shutil.which("bash")
    if os.name == "nt":
        bash = "C:/Program Files/Git/bin/bash.exe"
    assert bash, "bash is required to verify the workflow shell"
    state = dict(state="OPEN", isDraft=False, isCrossRepository=False, labels=[],
                 autoMergeRequest={} if pending else None, headRefOid="synthetic-head")
    state.update(updates)
    (tmp_path / "state.json").write_text(json.dumps(state))
    workflow = yaml.safe_load((ROOT / ".github/workflows/auto-merge.yml").read_text())
    script = workflow["jobs"]["reconcile"]["steps"][0]["run"]
    prelude = """
    gh() {
      if [[ "$2" == view ]]; then
        if [[ "$*" == *--jq* ]]; then echo "$READBACK"; else cat state.json; fi
      else
        echo "$GH_TOKEN $*" >> actions.txt
        return "$DISABLE_EXIT"
      fi
    }
    """
    script_path = tmp_path / "run.sh"
    script_path.write_text(prelude + script, encoding="utf-8")
    env = dict(os.environ, PR="1190", REPO="synthetic/repo", GH_TOKEN="synthetic-read",
               MERGE_TOKEN=token, DISABLE_EXIT=disable_exit, READBACK=readback)
    local_jq = ROOT / ".review-tools" / "jq.exe"
    if local_jq.exists():
        env["PATH"] = str(local_jq.parent) + os.pathsep + env["PATH"]
    result = subprocess.run([bash, "run.sh"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=15)
    assert (result.returncode == 0) == success, result.stderr
    actions_file = tmp_path / "actions.txt"
    actions = actions_file.read_text() if actions_file.exists() else ""
    if expected:
        assert expected in actions
        if expected == "--auto":
            assert "synthetic-pat pr merge" in actions
            assert "--match-head-commit synthetic-head" in actions
    else:
        assert actions == ""
