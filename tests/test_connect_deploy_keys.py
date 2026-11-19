"""Deployment must preserve existing Connect keys; all values here are synthetic."""
import re
from pathlib import Path


def test_deploy_preserves_connect_encryption_and_login_signing_keys():
    workflow = Path(".github/workflows/oracle-deploy.yml").read_text(encoding="utf-8")
    pattern = re.search(r"grep -E '([^']+)' \.env > /tmp/persisted_env_backup\.env", workflow)
    assert pattern is not None
    for name in ("JWT_SECRET", "TG_CONNECT_SESSION_KEY"):
        assert re.match(pattern.group(1), f"{name}=synthetic-test-value")
