# Oisha GitHub Actions Runner Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate GitHub account/runner infrastructure failures from application failures, restore isolated PR checks, and keep the production Oracle runner restricted to trusted jobs.

**Architecture:** Add a checkout-free GitHub-hosted probe and a trusted self-hosted probe. Emit machine-readable diagnostic summaries, verify workflow security contracts in pytest, and document the exact account-level remediation path for each observed failure class.

**Tech Stack:** GitHub Actions YAML, Bash, Python 3.11, pytest.

## Global Constraints

- Pull-request code never executes on `[self-hosted, oracle]`.
- The Oracle runner receives secrets only on trusted `main` deployment jobs.
- Diagnostic jobs do not install project dependencies.
- A job that never reaches step 1 is classified as infrastructure/account failure, not a test failure.
- No secret values, environment dumps, or token-bearing URLs enter artifacts.

---

## File Structure

- Create `.github/workflows/runner-diagnostics.yml`.
- Create `scripts/ci/oracle_runner_diagnostic.sh`.
- Create `scripts/ci/render_runner_diagnostic.py`.
- Modify `.github/workflows/test.yml` only after the probe succeeds.
- Create `tests/test_runner_workflow_contract.py`.
- Create `docs/operations/github-actions-runner-runbook.md`.

---

### Task 1: Add workflow security contract tests

**Files:**
- Create: `tests/test_runner_workflow_contract.py`

**Interfaces:**
- Produces: tests that prevent PR jobs from targeting production runner labels.
- Consumes: workflow YAML files as text/YAML.

- [ ] **Step 1: Write failing contract tests**

```python
from pathlib import Path
import yaml


def load_workflow(name: str):
    return yaml.safe_load(Path(f".github/workflows/{name}").read_text())


def test_pull_request_jobs_never_use_oracle_runner():
    workflow = load_workflow("test.yml")
    for job_name, job in workflow["jobs"].items():
        condition = str(job.get("if", ""))
        runs_on = job.get("runs-on")
        if "pull_request" in condition or not condition:
            assert runs_on != ["self-hosted", "oracle"], job_name


def test_runner_diagnostic_has_checkout_free_github_hosted_probe():
    workflow = load_workflow("runner-diagnostics.yml")
    probe = workflow["jobs"]["github-hosted-probe"]
    assert probe["runs-on"] == "ubuntu-latest"
    assert all("checkout" not in str(step.get("uses", "")) for step in probe["steps"])
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_runner_workflow_contract.py -q`
Expected: FAIL because `runner-diagnostics.yml` does not exist.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_runner_workflow_contract.py
git commit -m "test(ci): define runner isolation contract"
```

---

### Task 2: Add the minimal GitHub-hosted probe

**Files:**
- Create: `.github/workflows/runner-diagnostics.yml`

**Interfaces:**
- Produces: `github-hosted-probe` job with no checkout/dependency install.
- Consumes: GitHub runner metadata only.

- [ ] **Step 1: Implement the minimal workflow**

```yaml
name: Runner diagnostics

on:
  workflow_dispatch:
  pull_request:
    paths:
      - '.github/workflows/runner-diagnostics.yml'
      - 'tests/test_runner_workflow_contract.py'

permissions:
  contents: read

jobs:
  github-hosted-probe:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Reach step one
        run: echo "github-hosted-step-1-reached=true" >> "$GITHUB_STEP_SUMMARY"
      - name: Record safe runner metadata
        run: |
          {
            echo "runner_os=$RUNNER_OS"
            echo "runner_arch=$RUNNER_ARCH"
            echo "event=$GITHUB_EVENT_NAME"
            echo "repository=$GITHUB_REPOSITORY"
          } > runner-diagnostic.txt
      - uses: actions/upload-artifact@v4
        with:
          name: github-hosted-runner-diagnostic
          path: runner-diagnostic.txt
          retention-days: 3
```

- [ ] **Step 2: Verify YAML and contract**

Run: `pytest tests/test_runner_workflow_contract.py -q`
Expected: PASS for the GitHub-hosted probe assertions.

- [ ] **Step 3: Push and inspect the run**

Expected outcomes:

```text
queued with steps=None or completed failure before step 1 -> account/assignment blocker
step 1 reached and later failure -> workflow-level blocker
completed success -> GitHub-hosted capacity restored
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/runner-diagnostics.yml
git commit -m "ci: add checkout-free runner probe"
```

---

### Task 3: Add the trusted Oracle runner probe

**Files:**
- Create: `scripts/ci/oracle_runner_diagnostic.sh`
- Modify: `.github/workflows/runner-diagnostics.yml`
- Modify: `tests/test_runner_workflow_contract.py`

**Interfaces:**
- Produces: safe JSON/text diagnostic artifact.
- Consumes: trusted `workflow_dispatch` or `main` context only.

- [ ] **Step 1: Extend failing contract tests**

```python

def test_oracle_probe_is_never_available_to_pull_request_event():
    workflow_text = Path('.github/workflows/runner-diagnostics.yml').read_text()
    oracle_block = workflow_text.split('oracle-probe:', 1)[1]
    assert "github.event_name == 'workflow_dispatch'" in oracle_block
    assert "pull_request" not in oracle_block.split('steps:', 1)[0]
```

- [ ] **Step 2: Implement safe shell diagnostics**

```bash
#!/usr/bin/env bash
set -euo pipefail

printf 'runner_name=%s\n' "${RUNNER_NAME:-unknown}"
printf 'runner_os=%s\n' "${RUNNER_OS:-unknown}"
printf 'runner_arch=%s\n' "${RUNNER_ARCH:-unknown}"
printf 'workspace_writable=%s\n' "$(test -w "${GITHUB_WORKSPACE:-.}" && echo true || echo false)"
printf 'disk_free_kb=%s\n' "$(df -Pk "${GITHUB_WORKSPACE:-.}" | awk 'NR==2 {print $4}')"
printf 'docker_available=%s\n' "$(command -v docker >/dev/null && echo true || echo false)"
```

Do not print environment variables, process command lines, service tokens, or `.env` content.

- [ ] **Step 3: Add trusted job**

```yaml
  oracle-probe:
    if: github.event_name == 'workflow_dispatch'
    runs-on: [self-hosted, oracle]
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v7
      - name: Run safe diagnostic
        run: bash scripts/ci/oracle_runner_diagnostic.sh > oracle-runner-diagnostic.txt
      - uses: actions/upload-artifact@v4
        with:
          name: oracle-runner-diagnostic
          path: oracle-runner-diagnostic.txt
          retention-days: 3
```

- [ ] **Step 4: Verify contract**

Run: `pytest tests/test_runner_workflow_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/oracle_runner_diagnostic.sh .github/workflows/runner-diagnostics.yml tests/test_runner_workflow_contract.py
git commit -m "ci: add trusted Oracle runner diagnostics"
```

---

### Task 4: Produce deterministic diagnostic classification

**Files:**
- Create: `scripts/ci/render_runner_diagnostic.py`
- Create: `tests/test_runner_diagnostic_classifier.py`

**Interfaces:**
- Produces: `classify_run(run: dict, jobs: list[dict]) -> str`.
- Consumes: normalized workflow run/job metadata.

- [ ] **Step 1: Write failing classifier tests**

```python
from scripts.ci.render_runner_diagnostic import classify_run


def test_no_steps_is_account_or_assignment_failure():
    assert classify_run(
        {"status":"completed", "conclusion":"failure"},
        [{"status":"completed", "conclusion":"failure", "steps":None}],
    ) == "runner_or_account_before_step_one"


def test_failed_named_step_is_workflow_failure():
    assert classify_run(
        {"status":"completed", "conclusion":"failure"},
        [{"steps":[{"name":"Install", "conclusion":"failure"}]}],
    ) == "workflow_step_failure"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_runner_diagnostic_classifier.py -q`
Expected: FAIL because classifier does not exist.

- [ ] **Step 3: Implement classifier**

Return one of:

```text
queued_waiting_for_runner
runner_or_account_before_step_one
workflow_step_failure
workflow_success
cancelled
unknown
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_runner_diagnostic_classifier.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/render_runner_diagnostic.py tests/test_runner_diagnostic_classifier.py
git commit -m "ci: classify runner infrastructure failures"
```

---

### Task 5: Resolve the observed account/runner blocker

**Files:**
- Create: `docs/operations/github-actions-runner-runbook.md`

**Interfaces:**
- Consumes: diagnostic run evidence.
- Produces: exact remediation record and owner action when GitHub UI is required.

- [ ] **Step 1: Record the GitHub-hosted result**

Use this decision table:

```text
Probe never reaches step 1:
  Settings -> Billing and licensing -> Actions usage/spending
  Settings -> Actions -> General -> Actions permissions
  Account payment/restriction banners
  GitHub Status/Support case with run ID

Probe reaches step 1:
  fix the named failing workflow step instead of account settings
```

- [ ] **Step 2: Record the Oracle result**

```text
queued indefinitely -> runner offline, busy, or label mismatch
step 1 reached -> runner registration is healthy
workspace_writable=false -> service user/workspace ownership issue
disk_free_kb below 2 GB -> cleanup before trusted jobs
```

- [ ] **Step 3: Apply the single confirmed remediation**

Only change the setting indicated by evidence. Do not move PR workloads to Oracle as a workaround.

- [ ] **Step 4: Re-run both probes**

Acceptance:

```text
GitHub-hosted probe reaches and completes step 1
Oracle probe is online and completes only on manual trusted trigger
```

- [ ] **Step 5: Commit the runbook evidence**

```bash
git add docs/operations/github-actions-runner-runbook.md
git commit -m "docs(ci): record runner remediation procedure"
```

---

### Task 6: Restore isolated application CI

**Files:**
- Modify: `.github/workflows/test.yml`
- Modify: `tests/test_runner_workflow_contract.py`

**Interfaces:**
- Consumes: successful GitHub-hosted probe.
- Produces: working Python and TypeScript PR jobs on isolated runners.

- [ ] **Step 1: Assert required PR jobs**

```python

def test_pr_ci_has_python_and_typescript_jobs_on_ubuntu():
    workflow = load_workflow('test.yml')
    assert workflow['jobs']['pull-request-tests']['runs-on'] == 'ubuntu-latest'
    assert workflow['jobs']['typescript-monorepo']['runs-on'] == 'ubuntu-latest'
```

- [ ] **Step 2: Verify current status**

Run: `pytest tests/test_runner_workflow_contract.py -q`
Expected: PASS for YAML shape; remote run may still expose infrastructure state.

- [ ] **Step 3: Keep production job main-only**

The trusted Oracle job must include:

```yaml
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
runs-on: [self-hosted, oracle]
```

- [ ] **Step 4: Trigger a harmless PR and verify**

Expected:

```text
Python PR job: completed
TypeScript PR job: completed
No PR job assigned to Oracle
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/test.yml tests/test_runner_workflow_contract.py
git commit -m "ci: restore isolated Oisha pull request checks"
```

- [ ] **Step 6: Open PR**

PR title: `ci: diagnose and restore Oisha Actions runners`

PR evidence: both probe run IDs, first reached step, application CI results, and confirmation that Oracle remains trusted-main-only.
