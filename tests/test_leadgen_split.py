from unittest.mock import MagicMock, patch
import pytest

from src.services.core.crm.amocrm_pipeline_config import (
    UTC_PIPELINE_ID,
    UTC_NEW_STATUS_ID,
    TARGET_LEADS_INHOUSE_PIPELINE_ID,
    TARGET_LEADS_INHOUSE_NEW_STATUS_ID,
    ACTIVE_PIPELINE_IDS,
)
from src.services.core.instagram.leadgen_delivery import (
    get_lead_destination,
    get_next_lead_destination,
    save_crm_checkpoint,
    record_delivery_status,
)
from src.services.core.instagram.leadgen_sheets import (
    append_lead_to_sheet,
    OUTSOURCE_WORKSHEET_TITLE,
    INHOUSE_WORKSHEET_TITLE,
)


def test_pipeline_config_split_constants():
    assert UTC_PIPELINE_ID == 11322658
    assert UTC_NEW_STATUS_ID == 88756946
    # Inhouse Meta leadlari birlashtirilgan "Sotuv" voronkasining "Yangi" bosqichiga tushadi
    assert TARGET_LEADS_INHOUSE_PIPELINE_ID == 11162698
    assert TARGET_LEADS_INHOUSE_NEW_STATUS_ID == 87609514
    assert UTC_PIPELINE_ID in ACTIVE_PIPELINE_IDS
    assert TARGET_LEADS_INHOUSE_PIPELINE_ID in ACTIVE_PIPELINE_IDS


def test_alternating_lead_destination_logic():
    id1 = "lead_split_test_1"
    id2 = "lead_split_test_2"
    id3 = "lead_split_test_3"

    # Record lead 1 as utc
    record_delivery_status(id1, 101, True, True, True, destination="utc")
    assert get_lead_destination(id1) == "utc"

    # Next lead destination should be inhouse
    next_dest = get_next_lead_destination()
    assert next_dest == "inhouse"

    # Record lead 2 as inhouse
    record_delivery_status(id2, 102, True, True, True, destination="inhouse")
    assert get_lead_destination(id2) == "inhouse"

    # Next lead destination should alternate back to utc
    next_dest_2 = get_next_lead_destination()
    assert next_dest_2 == "utc"

    # Record lead 3 as utc
    save_crm_checkpoint(id3, 103, destination="utc")
    assert get_lead_destination(id3) == "utc"
    assert get_next_lead_destination() == "inhouse"


@patch("src.services.core.instagram.leadgen_sheets.get_leadgen_spreadsheet")
def test_append_lead_to_sheet_destinations(mock_get_sh):
    mock_sh = MagicMock()
    mock_ws_out = MagicMock()
    mock_ws_in = MagicMock()

    def mock_worksheet(title):
        if "outsource" in title.lower():
            return mock_ws_out
        return mock_ws_in

    mock_sh.worksheet.side_effect = mock_worksheet
    mock_get_sh.return_value = mock_sh

    # 1. Test UTC destination routes to outsource worksheet
    res_utc = append_lead_to_sheet(
        leadgen_id="utc_lead_1",
        lead_id=5001,
        fields={"ism": "Ali", "tel": "998901234567"},
        destination="utc",
    )
    assert res_utc is True
    assert mock_ws_out.append_row.called

    # 2. Test Inhouse destination routes to inhouse worksheet
    res_inhouse = append_lead_to_sheet(
        leadgen_id="inhouse_lead_1",
        lead_id=5002,
        fields={"ism": "Vali", "tel": "998907654321"},
        destination="inhouse",
    )
    assert res_inhouse is True
    assert mock_ws_in.append_row.called
