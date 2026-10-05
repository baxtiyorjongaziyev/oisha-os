import os
import subprocess  # nosec B404 - bounded offline pytest regression
import sys
from pathlib import Path
import pytest


@pytest.mark.parametrize('target,expected', [
    ('tests/test_amocrm_retry.py', '7 passed'),
    ('tests/test_call_analyzer.py', '27 passed'),
    ('tests/test_customer_360.py', '4 passed'),
])
def test_unit_suite_exits_without_leaking_sqlite_worker(target, expected):
    env = dict(os.environ, SKIP_LIVE='1', ALLOW_LOCAL_RUN='0',
               GITHUB_ACTIONS='false', FORCE_PYTEST_EXIT='0')
    result = subprocess.run(  # nosec B603 - fixed interpreter and test target
        [sys.executable, '-m', 'pytest', '-q', target],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected in result.stdout
