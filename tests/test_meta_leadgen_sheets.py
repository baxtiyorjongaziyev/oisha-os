from unittest.mock import MagicMock, patch
import pytest

from src.services.core.instagram.leadgen_sheets import (
    format_lead_row,
    append_lead_to_sheet,
    clean_phone,
    humanize_stage,
    humanize_goal,
    humanize_sector,
    HEADERS,
)


def test_clean_phone():
    assert clean_phone("998911780850") == "'+998 (91) 178-08-50"
    assert clean_phone("+998901234567") == "'+998 (90) 123-45-67"
    assert clean_phone("901234567") == "'+998 (90) 123-45-67"


def test_humanizers():
    assert humanize_stage("mahsulotim_bor,_lekin_brendni_himoyalamaganman") == "Mahsulot bor (brend ochiq)"
    assert humanize_goal("brend_nomini_qonuniy_himoyalash") == "Patentlash va Himoya"
    assert humanize_sector("savdo") == "Savdo"


def test_format_lead_row():
    fields = {
        "ismingiz": "Akbar",
        "telefon_raqamingz": "+998901234567",
        "faoliyat_sohasi": "savdo",
        "tadbirkorlik_holati": "yangi_biznes",
        "asosiy_maqsad": "patent",
        "brendingiz": "Akbar Brand",
    }
    row = format_lead_row(
        leadgen_id="12345",
        lead_id=98765,
        fields=fields,
        form_name="patent brend new forma | 12.09",
        created_time="2026-09-18 17:00:00",
    )

    assert len(row) == len(HEADERS)
    assert row[0] == "=ROW()-1"
    assert row[1] == "18.09.2026 17:00"
    assert row[2] == "Akbar"
    assert row[3] == "'+998 (90) 123-45-67"
    assert row[4] == "Savdo"
    assert row[5] == "Yangi biznes boshlash"
    assert row[6] == "Patentlash va Himoya"
    assert row[7] == "Akbar Brand"
    assert "98765" in row[8]
    assert row[9] == "Patent Brend (12.09)"
    assert row[11] == "12345"


@patch("src.services.core.instagram.leadgen_sheets.get_leadgen_spreadsheet")
def test_append_lead_to_sheet_success(mock_get_sh):
    mock_sh = MagicMock()
    mock_ws = MagicMock()
    mock_sh.worksheet.return_value = mock_ws
    mock_get_sh.return_value = mock_sh

    res = append_lead_to_sheet(
        leadgen_id="111",
        lead_id=222,
        fields={"ism": "Ali", "tel": "998901112233"},
        form_name="form1",
    )

    assert res is True
    assert mock_ws.append_row.called


def test_format_lead_row_outsource():
    fields = {"ism": "Vali", "tel": "+998901234567"}
    row = format_lead_row(
        leadgen_id="999",
        lead_id=888,
        fields=fields,
        is_outsource=True,
    )
    assert len(row) == 13
    assert row[10] == "0 ta qo'ng'iroq"
