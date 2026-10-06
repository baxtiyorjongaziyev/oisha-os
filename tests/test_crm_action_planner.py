from src.services.call_analytics.crm_actions import (
    CrmActionPlanner,
    FieldFillAction,
    FieldSuggestion,
    StageAction,
    TaskAction,
)

FIELD_MAP = {"mijoz_kompaniya": 101, "mijoz_lavozimi": 102, "joylashuv": 103}
STAGE_RULES = {
    "pipeline_order": [10, 20, 30, 40],
    "outcome_to_status": {"uchrashuv_belgilandi": 30, "qiziqdi": 20},
    "terminal_outcomes": ["sotildi", "rad_etdi"],
    "min_confidence": 0.8,
}


def _lead(status_id=20, fields=None):
    return {
        "id": 1,
        "status_id": status_id,
        "custom_fields_values": [
            {"field_id": fid, "values": [{"value": val}]} for fid, val in (fields or {}).items()
        ],
    }


def _plan(analysis, lead):
    return CrmActionPlanner(FIELD_MAP, STAGE_RULES).plan(analysis, lead)


def _of(actions, kind):
    return [a for a in actions if isinstance(a, kind)]


def test_fills_only_empty_fields_and_suggests_for_filled():
    actions = _plan(
        {"mijoz_kompaniya": "Acme", "mijoz_lavozimi": "CEO", "joylashuv": ""},
        _lead(fields={102: "Manager"}),
    )
    assert _of(actions, FieldFillAction) == [FieldFillAction(field_id=101, value="Acme")]
    assert _of(actions, FieldSuggestion) == [
        FieldSuggestion(field_id=102, current="Manager", proposed="CEO")
    ]


def test_same_value_produces_no_suggestion():
    actions = _plan({"mijoz_lavozimi": "CEO"}, _lead(fields={102: "CEO"}))
    assert _of(actions, FieldSuggestion) == []
    assert _of(actions, FieldFillAction) == []


def test_moves_stage_forward_when_confident():
    actions = _plan({"natija": "uchrashuv_belgilandi", "natija_ishonch": 0.9}, _lead(20))
    assert _of(actions, StageAction) == [StageAction(from_status=20, to_status=30)]


def test_low_confidence_does_not_move_stage():
    actions = _plan({"natija": "uchrashuv_belgilandi", "natija_ishonch": 0.5}, _lead(20))
    assert _of(actions, StageAction) == []


def test_backward_move_becomes_manager_task():
    actions = _plan({"natija": "qiziqdi", "natija_ishonch": 0.95}, _lead(40))
    assert _of(actions, StageAction) == []
    tasks = _of(actions, TaskAction)
    assert len(tasks) == 1 and "etap" in tasks[0].text.lower()


def test_terminal_outcome_never_moves_stage():
    actions = _plan({"natija": "rad_etdi", "natija_ishonch": 0.99}, _lead(20))
    assert _of(actions, StageAction) == []
    assert len(_of(actions, TaskAction)) == 1


def test_unknown_status_in_pipeline_is_skipped():
    actions = _plan({"natija": "uchrashuv_belgilandi", "natija_ishonch": 0.9}, _lead(999))
    assert _of(actions, StageAction) == []


def test_production_config_is_consistent():
    from src.services.call_analytics import crm_automation_config as cfg

    order = cfg.STAGE_RULES["pipeline_order"]
    assert len(order) == len(set(order)) == 5
    assert set(cfg.STAGE_RULES["outcome_to_status"].values()) <= set(order)
    planner = CrmActionPlanner(cfg.FIELD_MAP, cfg.STAGE_RULES)
    actions = planner.plan(
        {"natija": "uchrashuv_kelishildi", "natija_ishonch": 0.9, "mijoz_kompaniya": "Acme"},
        _lead(status_id=cfg.STATUS_ALOQA),
    )
    assert StageAction(cfg.STATUS_ALOQA, cfg.STATUS_UCHRASHUV) in actions
    assert FieldFillAction(cfg.FIELD_BRAND_NAME, "Acme") in actions


def test_closed_won_or_lost_lead_is_never_touched():
    from src.services.call_analytics import crm_automation_config as cfg

    planner = CrmActionPlanner(cfg.FIELD_MAP, cfg.STAGE_RULES)
    analysis = {"natija": "rad_etdi", "natija_ishonch": 0.99, "mijoz_kompaniya": "Acme"}
    for status in (cfg.STATUS_WON, cfg.STATUS_LOST):
        assert planner.plan(analysis, _lead(status_id=status)) == []
    assert cfg.STATUS_WON not in cfg.STAGE_RULES["outcome_to_status"].values()
    assert cfg.STATUS_LOST not in cfg.STAGE_RULES["outcome_to_status"].values()


def test_placeholder_values_are_never_written():
    for placeholder in ("N/A", "n/a", "-", "Noaniq", "yo'q", "null", "None"):
        actions = _plan({"mijoz_kompaniya": placeholder}, _lead())
        assert _of(actions, FieldFillAction) == [], placeholder
