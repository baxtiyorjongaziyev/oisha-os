import dataclasses
import enum
import json
from pathlib import Path

from src.services.core.service_config.modules import get_default_modules

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "service_default_modules.json"


def _enc(o):
    if isinstance(o, enum.Enum):
        return o.value
    raise TypeError(o)


def _dump(modules):
    return json.loads(json.dumps(
        [[k.value, dataclasses.asdict(v)] for k, v in modules.items()], default=_enc
    ))


def test_default_modules_match_snapshot():
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert _dump(get_default_modules()) == expected


def test_default_modules_returns_fresh_objects():
    first, second = get_default_modules(), get_default_modules()
    for key in first:
        assert first[key] is not second[key]
        assert first[key].deliverables is not second[key].deliverables
