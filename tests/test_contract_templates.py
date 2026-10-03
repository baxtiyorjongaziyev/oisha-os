import dataclasses
import json
from pathlib import Path

from src.agents.contracts.templates import load_contract_templates

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "contract_templates.json"


def test_contract_templates_match_snapshot():
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = [[k, dataclasses.asdict(v)] for k, v in load_contract_templates().items()]
    assert actual == expected


def test_contract_templates_return_fresh_objects():
    first, second = load_contract_templates(), load_contract_templates()
    for key in first:
        assert first[key] is not second[key]
        assert first[key].clauses is not second[key].clauses
