from datetime import datetime

import pytest

from scripts.amocrm_merge_sales_pipeline import (
    AmoCRMSalesFarmerMigration,
    CONFIRM_TEXT,
)
from src.services.core.amocrm_pipeline_config import (
    CLOSER_TO_SALES_STATUS_NAME,
    FARMER_PIPELINE_ID,
    FINAL_PAYMENT_TASK_TEXT,
    LEGACY_CLOSER_PIPELINE_ID,
    SALES_ADVANCE_STATUS_NAME,
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)


def _migration(live=False):
    migration = AmoCRMSalesFarmerMigration.__new__(AmoCRMSalesFarmerMigration)
    migration.live = live
    migration.confirm = CONFIRM_TEXT if live else ""
    migration.actions = []
    migration.errors = []
    migration.now = datetime(2026, 6, 4, 12, 0, 0)
    return migration


def test_closer_statuses_map_to_sales_statuses():
    assert CLOSER_TO_SALES_STATUS_NAME["Brief / Ehtiyoj aniqlandi"] == "Brief / Ehtiyoj aniqlandi"
    assert CLOSER_TO_SALES_STATUS_NAME[SALES_ADVANCE_STATUS_NAME] == SALES_ADVANCE_STATUS_NAME
    assert CLOSER_TO_SALES_STATUS_NAME["Неразобранное"] == "Yangi so'rov"


def test_live_requires_confirm_before_network_calls():
    migration = _migration(live=True)
    migration.confirm = "wrong"

    with pytest.raises(SystemExit):
        migration.run()


def test_migrate_lead_dry_run_records_without_patch():
    migration = _migration(live=False)
    migration.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no request in dry-run"))
    lead = {"id": 11, "pipeline_id": 10123314, "status_id": 80215318}

    migration.migrate_lead(lead, FARMER_PIPELINE_ID, 80215334, "test")

    assert migration.actions == [
        {
            "action": "lead_would_move",
            "lead_id": 11,
            "from_pipeline_id": 10123314,
            "from_status_id": 80215318,
            "to_pipeline_id": FARMER_PIPELINE_ID,
            "to_status_id": 80215334,
            "reason": "test",
        }
    ]


def test_dry_run_defers_closer_lead_move_when_sales_status_will_be_created():
    migration = _migration(live=False)
    migration.fetch_pipelines = lambda: [
        {
            "id": SALES_PIPELINE_ID,
            "name": "Hunter",
            "_embedded": {"statuses": [{"id": 801, "name": "Yangi so'rov", "sort": 10}]},
        },
        {
            "id": LEGACY_CLOSER_PIPELINE_ID,
            "name": "Closer",
            "_embedded": {
                "statuses": [
                    {"id": 901, "name": "Brief / Ehtiyoj aniqlandi", "sort": 10},
                ]
            },
        },
        {"id": FARMER_PIPELINE_ID, "name": "Farmer", "_embedded": {"statuses": []}},
    ]
    migration.fetch_active_pipeline_leads = lambda pipeline_id: (
        [{"id": 77, "pipeline_id": LEGACY_CLOSER_PIPELINE_ID, "status_id": 901}]
        if pipeline_id == LEGACY_CLOSER_PIPELINE_ID
        else []
    )
    migration.fetch_paginated = lambda *args, **kwargs: []
    migration.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no request in dry-run"))

    result = migration.run()

    assert result["success"] is True
    assert any(
        action["action"] == "lead_would_move_after_status_create"
        and action["lead_id"] == 77
        and action["target_status_name"] == "Brief / Ehtiyoj aniqlandi"
        for action in result["actions"]
    )
    assert not any(action["action"] == "lead_move_skipped_missing_sales_status" for action in result["actions"])


def test_legacy_closer_advance_hands_off_directly_to_farmer_start():
    migration = _migration(live=False)
    migration.fetch_pipelines = lambda: [
        {
            "id": SALES_PIPELINE_ID,
            "name": "Hunter",
            "_embedded": {"statuses": [{"id": 801, "name": "Yangi so'rov", "sort": 10}]},
        },
        {
            "id": LEGACY_CLOSER_PIPELINE_ID,
            "name": "Closer",
            "_embedded": {
                "statuses": [
                    {"id": 902, "name": SALES_ADVANCE_STATUS_NAME, "sort": 10},
                ]
            },
        },
        {
            "id": FARMER_PIPELINE_ID,
            "name": "Farmer",
            "_embedded": {
                "statuses": [
                    {"id": 1001, "name": "Loyiha va Brief", "sort": 10},
                ]
            },
        },
    ]
    migration.fetch_active_pipeline_leads = lambda pipeline_id: (
        [{"id": 88, "pipeline_id": LEGACY_CLOSER_PIPELINE_ID, "status_id": 902}]
        if pipeline_id == LEGACY_CLOSER_PIPELINE_ID
        else []
    )
    migration.fetch_paginated = lambda *args, **kwargs: []
    migration.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no request in dry-run"))

    result = migration.run()

    assert any(
        action["action"] == "lead_would_move"
        and action["lead_id"] == 88
        and action["to_pipeline_id"] == FARMER_PIPELINE_ID
        and action["to_status_id"] == 1001
        and action["reason"] == f"legacy_advance_to_farmer_start:{SALES_ADVANCE_STATUS_NAME}"
        for action in result["actions"]
    )


def test_final_payment_task_dry_run_for_pending_farmer_leads():
    migration = _migration(live=False)
    migration.fetch_active_pipeline_leads = lambda pipeline_id: [
        {"id": 1001, "status_id": 9001, "responsible_user_id": 55},
        {"id": 1002, "status_id": 1234},
    ]
    migration.fetch_paginated = lambda *args, **kwargs: []
    migration.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no request in dry-run"))

    migration.create_final_payment_tasks(9001)

    assert migration.actions == [
        {
            "action": "task_would_create",
            "lead_id": 1001,
            "task_text": FINAL_PAYMENT_TASK_TEXT,
        }
    ]


def test_won_lost_ids_are_never_active_migration_candidates():
    assert {STATUS_WON, STATUS_LOST} == {142, 143}
