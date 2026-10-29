import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.core.metasell.cards import build_team_report
from src.services.core.metasell.engine import MetaSellConversionEngine
from src.services.core.metasell.models import ConversionTrend, SellerDiagnosis

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "metasell_team_reports.json"


def _diag(name="Ali", **kwargs):
    values = dict(manager_name=name, total_calls=6, converted_calls=3,
                  conversion_rate=50.0, avg_score=75.0)
    values.update(kwargs)
    return SellerDiagnosis(**values)


def _volume(total=10, rate=50.0):
    return SimpleNamespace(total=total, answered=5, missed=total - 5,
                           answer_rate=rate, avg_duration_label="02:15")


CASES = {
    "empty": ([], None, None),
    "insufficient": ([_diag(total_calls=5)], None, {"__team__": object()}),
    "minimum_no_volumes": ([_diag()], None, None),
    "zero_team_volume": ([_diag()], None, {"__team__": _volume(0)}),
    "negative_team_volume": ([_diag()], None, {"__team__": _volume(-1)}),
    "unreliable_trend": ([_diag()], ConversionTrend(7, 50, 0, 6, 0, False, "kam"), {}),
    "full": (
        [_diag("Bek", converted_calls=0, conversion_rate=0, avg_score=90,
               growth_stage="unknown", revenue_at_risk=2_000_000),
         _diag("Ali", converted_calls=6, conversion_rate=100, growth_stage="ehtiyojlar",
               revenue_won=3_000_000),
         _diag("Excluded", total_calls=5, revenue_won=99_000_000)],
        ConversionTrend(7, 50, 20, 10, 10, True),
        {"__team__": _volume(20), "Later": _volume(10, 60),
         "First": _volume(5, 20), "Tie": _volume(10, 20),
         "Boundary": _volume(5, 80), "Tiny": _volume(4, 0)},
    ),
    "score_boundary": (
        [_diag("At", conversion_rate=0, avg_score=75),
         _diag("Below", conversion_rate=0, avg_score=74.9),
         _diag("Equal", conversion_rate=50, avg_score=90),
         _diag("Above", conversion_rate=100)], None, None,
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_team_report_preserves_text_inputs_and_logs(name, caplog):
    diagnoses, trend, volumes = deepcopy(CASES[name])
    before = deepcopy((diagnoses, trend, volumes))
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[name]
    with caplog.at_level("DEBUG"):
        assert build_team_report(diagnoses, trend, volumes) == expected
        assert MetaSellConversionEngine(None).build_team_report(diagnoses, trend, volumes) == expected
    # The insufficient-data volume is deliberately unreadable: early return must win.
    if name != "insufficient":
        assert (diagnoses, trend, volumes) == before
    assert not caplog.records
