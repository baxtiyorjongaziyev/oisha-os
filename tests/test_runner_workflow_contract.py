from pathlib import Path

import yaml


def load_workflow(name: str):
    return yaml.safe_load(Path(f".github/workflows/{name}").read_text(encoding="utf-8"))


def test_pull_request_jobs_never_use_oracle_runner():
    workflow = load_workflow("test.yml")
    for job_name, job in workflow["jobs"].items():
        condition = str(job.get("if", ""))
        runs_on = job.get("runs-on")
        if "pull_request" in condition or not condition:
            assert runs_on != ["self-hosted", "oracle"], job_name


def test_pr_ci_has_python_and_typescript_jobs_on_ubuntu():
    workflow = load_workflow("test.yml")
    assert workflow["jobs"]["pull-request-tests"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["typescript-monorepo"]["runs-on"] == "ubuntu-latest"


def test_trusted_main_job_is_push_only():
    workflow = load_workflow("test.yml")
    trusted = workflow["jobs"]["trusted-main-tests"]
    assert "github.event_name == 'push'" in trusted["if"]
    assert trusted["runs-on"] == "ubuntu-latest"


def test_runner_diagnostic_has_action_free_github_hosted_probe():
    workflow = load_workflow("runner-diagnostics.yml")
    probe = workflow["jobs"]["github-hosted-probe"]
    assert probe["runs-on"] == "ubuntu-latest"
    assert all("uses" not in step for step in probe["steps"])
    assert probe["steps"][0]["name"] == "Reach step one"


def test_oracle_probe_is_trusted_main_only_and_has_no_secrets():
    workflow_text = Path(".github/workflows/runner-diagnostics.yml").read_text(encoding="utf-8")
    oracle_block = workflow_text.split("oracle-probe:", 1)[1]
    pre_steps = oracle_block.split("steps:", 1)[0]
    assert "github.ref == 'refs/heads/main'" in pre_steps
    assert "github.event_name == 'workflow_dispatch'" in pre_steps
    assert "github.event_name == 'push'" in pre_steps
    assert "pull_request" not in pre_steps
    assert "secrets." not in oracle_block
    assert "[self-hosted, oracle]" in oracle_block


DRAFT_GATED_JOBS = {
    "test.yml": ["changes", "pull-request-tests"],
    "gitleaks.yml": ["gitleaks"],
    "oracle-deploy.yml": ["import-guard"],
}


def test_pr_jobs_skip_draft_pull_requests_to_save_actions_minutes():
    for name, jobs in DRAFT_GATED_JOBS.items():
        workflow = load_workflow(name)
        # PyYAML parses the bare `on:` key as boolean True.
        types = workflow[True]["pull_request"]["types"]
        assert "ready_for_review" in types, name
        for job in jobs:
            condition = str(workflow["jobs"][job]["if"])
            assert "github.event.pull_request.draft == false" in condition, (name, job)


def test_uzbek_guard_runs_inside_import_guard_on_pull_requests():
    guard = load_workflow("uzbek-text-guard.yml")
    assert "pull_request" not in guard[True]
    steps = load_workflow("oracle-deploy.yml")["jobs"]["import-guard"]["steps"]
    assert any("check_uzbek_text.py --base" in str(step.get("run", "")) for step in steps)


def test_labeler_does_not_run_on_every_push():
    types = load_workflow("labeler.yml")[True]["pull_request_target"]["types"]
    assert "synchronize" not in types


def test_manual_deploy_is_main_only_confirmed_and_does_not_need_hosted_runner():
    workflow = load_workflow("oracle-deploy.yml")
    guard = workflow["jobs"]["manual-guard"]
    condition = str(guard["if"])
    assert guard["runs-on"] == ["self-hosted", "oracle"]
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "github.ref == 'refs/heads/main'" in condition
    assert "inputs.confirm == 'DEPLOY_PRODUCTION'" in condition
    assert "pull_request" not in condition
    # The self-hosted guard must stay cheap: no dependency install, no pytest.
    runs = " ".join(str(step.get("run", "")) for step in guard["steps"])
    assert "compileall" in runs
    assert "pip install" not in runs and "pytest" not in runs


def test_deploy_requires_a_passed_guard_for_each_trigger():
    workflow = load_workflow("oracle-deploy.yml")
    deploy = workflow["jobs"]["deploy"]
    condition = str(deploy["if"])
    assert set(deploy["needs"]) == {"import-guard", "manual-guard"}
    assert "github.event_name == 'push' && needs.import-guard.result == 'success'" in condition
    assert "github.event_name == 'workflow_dispatch' && needs.manual-guard.result == 'success'" in condition
    assert "always()" in condition  # skipped manual-guard must not block push deploys
    assert "pull_request" not in condition
    # Hosted import-guard is skipped on manual runs so they do not burn minutes.
    assert "github.event_name != 'workflow_dispatch'" in str(workflow["jobs"]["import-guard"]["if"])


def test_all_workflows_valid_yaml_and_no_secrets_in_step_if():
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(doc, dict) and "jobs" in doc, path.name
        for job_name, job in doc["jobs"].items():
            for idx, step in enumerate(job.get("steps", [])):
                cond = str(step.get("if", ""))
                assert "secrets." not in cond, (path.name, job_name, idx, cond)


def test_self_hosted_workflows_never_ssh_to_dead_oracle_host():
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        if path.name == "userbot-vps.yml":
            continue
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        uses_self_hosted = any(
            "oracle" in (j.get("runs-on") if isinstance(j.get("runs-on"), list) else [j.get("runs-on")])
            for j in doc["jobs"].values()
        )
        if uses_self_hosted:
            assert "appleboy/ssh-action" not in text, path.name
            assert "ORACLE_HOST" not in text, path.name


def test_deploy_workflow_targets_hetzner_and_preserves_live_env():
    text = Path(".github/workflows/oracle-deploy.yml").read_text(encoding="utf-8")
    assert "/home/deploy/oisha-os" in text
    assert "oisha.service" in text
    assert "git init -b main" in text
    assert "if [ -s .env ]; then" in text


def test_followup_pr_checks_out_main_and_handles_deleted_branch():
    workflow = load_workflow("followup-pr.yml")
    steps = workflow["jobs"]["followup"]["steps"]
    checkout = steps[0]
    assert checkout["with"]["ref"] == "main"
    run_script = next(s["run"] for s in steps if "followup_pr.py" in str(s.get("run", "")))
    assert "git ls-remote --exit-code --heads origin" in run_script


def test_oisha_web_workflow_narrow_paths_and_no_oracle_ssh():
    text = Path(".github/workflows/oisha-web.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    paths = workflow[True]["push"]["paths"]
    assert "deploy/**" not in paths
    assert "ORACLE_HOST" not in text
    assert "appleboy/ssh-action" not in text
    assert workflow["jobs"]["build"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["deploy"]["needs"] == "build"
