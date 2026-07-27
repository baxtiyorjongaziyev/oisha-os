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


def test_pr_ci_has_python_and_typescript_jobs_on_ubuntu():
    workflow = load_workflow("test.yml")
    assert workflow["jobs"]["pull-request-tests"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["typescript-monorepo"]["runs-on"] == "ubuntu-latest"


def test_trusted_main_job_is_push_only():
    workflow = load_workflow("test.yml")
    trusted = workflow["jobs"]["trusted-main-tests"]
    assert "github.event_name == 'push'" in trusted["if"]
    assert trusted["runs-on"] == ["self-hosted", "oracle"]


def test_runner_diagnostic_has_action_free_github_hosted_probe():
    workflow = load_workflow("runner-diagnostics.yml")
    probe = workflow["jobs"]["github-hosted-probe"]
    assert probe["runs-on"] == "ubuntu-latest"
    assert all("uses" not in step for step in probe["steps"])
    assert probe["steps"][0]["name"] == "Reach step one"


def test_oracle_probe_is_trusted_main_only_and_has_no_secrets():
    workflow_text = Path(".github/workflows/runner-diagnostics.yml").read_text()
    oracle_block = workflow_text.split("oracle-probe:", 1)[1]
    pre_steps = oracle_block.split("steps:", 1)[0]
    assert "github.ref == 'refs/heads/main'" in pre_steps
    assert "github.event_name == 'workflow_dispatch'" in pre_steps
    assert "github.event_name == 'push'" in pre_steps
    assert "pull_request" not in pre_steps
    assert "secrets." not in oracle_block
    assert "[self-hosted, oracle]" in oracle_block
