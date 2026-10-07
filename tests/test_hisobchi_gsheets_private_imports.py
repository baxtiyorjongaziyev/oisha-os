"""`from constants import *` skips underscore names, so the gsheets mixins
raised NameError for _get/_normalize_merchant/_fingerprint in prod
(2026-10-07, card_bot_handler -> get_known_rule)."""
import importlib
import re
from pathlib import Path

import pytest

import src.services.core.finance.gsheets.constants as constants

HELPERS = {
    name for name in vars(constants)
    if name.startswith("_") and not name.startswith("__")
}
MODULES = ["budget_salary", "client", "reporting", "transactions"]


@pytest.mark.parametrize("name", MODULES)
def test_mixin_resolves_every_constants_helper_it_calls(name):
    module = importlib.import_module(f"src.services.core.finance.gsheets.{name}")
    source = Path(module.__file__).read_text(encoding="utf-8")
    called = set(re.findall(r"(?<![\w.])(_[a-z][a-z0-9_]*)\(", source))
    missing = sorted(n for n in called & HELPERS if not hasattr(module, n))
    assert not missing, f"{name} calls undefined helpers: {missing}"
