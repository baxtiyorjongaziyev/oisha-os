from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_run_cleanup_requires_explicit_confirmation():
    workflow = ROOT / ".github" / "workflows" / "delete-cloud-run.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "push:" not in text
    assert "DELETE_OISHA_CLOUD_RUN" in text
    assert "confirm_cleanup" in text


def test_legacy_gcp_scripts_require_explicit_opt_in():
    guarded_files = [
        ROOT / "scripts" / "deploy-final.bat",
        ROOT / "scripts" / "setup-ci-cd.sh",
        ROOT / "scripts" / "reanimate_bot.py",
        ROOT / "src" / "sync_secrets_to_gcp.py",
    ]

    for path in guarded_files:
        text = path.read_text(encoding="utf-8")
        assert "OISHA_ALLOW_GCP" in text, f"{path} must require explicit GCP opt-in"


def test_health_check_defaults_to_oracle_local_service():
    text = (ROOT / "scripts" / "health_check.py").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8080/healthz/" in text
    assert "oisha-master-bot-4h4lsnzlsq-ey.a.run.app" not in text


def test_no_hardcoded_telegram_bot_token_in_reanimate_script():
    text = (ROOT / "scripts" / "reanimate_bot.py").read_text(encoding="utf-8")

    assert "8343217526:" not in text
