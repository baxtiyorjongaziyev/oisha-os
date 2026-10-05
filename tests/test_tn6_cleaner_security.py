"""Regression coverage for TN suffix cleaning without catastrophic backtracking."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def cleaner():
    path = Path(__file__).parents[1] / "scripts" / "test_tn6_cleaner.py"
    spec = importlib.util.spec_from_file_location("tn6_cleaner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.clean_contact_name


@pytest.mark.parametrize("value,expected", [
    ("Ali TN6 Gr", "Ali"),
    ("Ali TN6 TN2 gr", "Ali"),
    ("Ali Tez Natija 6", "Ali"),
    ("Ali TN", "Ali"),
    ("Ali TN6 middle", "Ali TN6 middle"),
    ("---Ali TN6---", "Ali TN6"),
    ("998901234567 TN6", "998901234567"),
])
def test_suffix_behavior(cleaner, value, expected):
    assert cleaner(value) == expected


def test_repeated_near_match_has_bounded_runtime():
    # A subprocess timeout bounds the test even if the old regex is restored.
    import subprocess
    import sys
    script = Path(__file__).parents[1] / "scripts" / "test_tn6_cleaner.py"
    code = (
        "import runpy; m=runpy.run_path(" + repr(str(script)) + "); "
        "s='Ali ' + 'TN6 ' * 2000 + '!'; "
        "assert m['clean_contact_name'](s) == s[:-1].strip()"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=5)
