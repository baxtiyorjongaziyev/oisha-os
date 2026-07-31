from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_telegram_mcp_is_not_publicly_exposed():
    nginx = (REPO_ROOT / "deploy" / "nginx-oisha.conf").read_text(encoding="utf-8")
    block = nginx.split("location /telegram-mcp", 1)[1].split("location /api/", 1)[0]

    assert 'auth_basic "Oisha Admin";' in block
    assert "auth_basic off;" not in block


def test_pull_requests_never_run_on_production_oracle_runner():
    workflow = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "pull-request-tests:" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow


def test_main_tests_are_push_only_and_isolated_from_production():
    workflow = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "trusted-main-tests:" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "if: github.event_name == 'push'" in workflow
