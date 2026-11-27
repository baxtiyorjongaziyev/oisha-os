import asyncio

from src.services.call_analytics import crm_automation_config as cfg
from src.services.call_analytics.crm_automation_hook import run_crm_automation
from tests.test_crm_automation_store import FakeDb
from tests.test_crm_executor import FakeAmo

ANALYSIS = {
    "natija": "uchrashuv_kelishildi",
    "natija_ishonch": 0.9,
    "mijoz_kompaniya": "Acme",
    "mijoz_kompaniya_ishonch": 1.0,
}


class LeadAmo(FakeAmo):
    def __init__(self, status_id=cfg.STATUS_ALOQA, ok=True):
        super().__init__(ok)
        self.status_id = status_id

    async def get_lead(self, lead_id):
        return {"id": lead_id, "status_id": self.status_id, "custom_fields_values": []}


def _run(state, amo):
    return asyncio.run(run_crm_automation(FakeDb(state), amo, 5, ANALYSIS))


def test_can_be_disabled_via_state():
    amo = LeadAmo()
    assert _run({"crm_automation:enabled": "off"}, amo) is None
    assert amo.calls == []


def test_dry_run_via_state_skips_amocrm_writes():
    amo = LeadAmo()
    result = _run({"crm_automation:enabled": "on", "crm_automation:dry_run": "on"}, amo)
    assert amo.calls == []
    assert len(result.audit_ids) == 2


def test_default_live_mode_writes_to_amocrm():
    amo = LeadAmo()
    _run({}, amo)
    assert ("status", 5, cfg.STATUS_UCHRASHUV) in amo.calls
    assert ("fields", 5, {cfg.FIELD_BRAND_NAME: "Acme"}) in amo.calls


def test_exception_never_propagates():
    class Broken(LeadAmo):
        async def get_lead(self, lead_id):
            raise RuntimeError("amo down")

    assert _run({"crm_automation:enabled": "on"}, Broken()) is None


def test_won_lead_untouched_even_live():
    amo = LeadAmo(status_id=cfg.STATUS_WON)
    _run({"crm_automation:enabled": "on", "crm_automation:dry_run": "off"}, amo)
    assert amo.calls == []


def test_normalizer_emits_clamped_outcome_confidence():
    from src.services.call_analytics.normalizer import _normalise_outcome_confidence

    assert _normalise_outcome_confidence("0.9") == 0.9
    assert _normalise_outcome_confidence(1.7) == 1.0
    assert _normalise_outcome_confidence(-1) == 0.0
    assert _normalise_outcome_confidence("abc") == 0.0
    assert _normalise_outcome_confidence(None) == 0.0


def test_low_field_confidence_skips_card_fill():
    from src.services.call_analytics.crm_actions import CrmActionPlanner, FieldFillAction

    planner = CrmActionPlanner(cfg.FIELD_MAP, cfg.STAGE_RULES)
    lead = {"id": 5, "status_id": cfg.STATUS_ALOQA, "custom_fields_values": []}
    uncertain = {**ANALYSIS, "mijoz_kompaniya_ishonch": 0.85}
    actions = planner.plan(uncertain, lead)
    assert not any(isinstance(a, FieldFillAction) for a in actions)
