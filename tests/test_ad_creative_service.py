"""Tests for Ad Creative resolution and amoCRM custom field mapping."""
from __future__ import annotations

import pytest

from src.services.core.marketing.ad_creative_service import (
    AdCreativeDetails,
    infer_creative_type,
    resolve_ad_creative,
    save_creative,
    get_stored_creative,
)
from src.services.core.instagram.leadgen_custom_fields import (
    FIELD_CREATIVE_URL,
    FIELD_CREATIVE_NAME,
    FIELD_UTM_CONTENT,
    FIELD_OPENSTAT_AD,
    extract_lead_custom_fields,
)
from src.services.core.instagram.leadgen_formatter import (
    build_leadgen_note,
    build_telegram_message,
)


def test_infer_creative_type():
    assert infer_creative_type("V6 - Brending") == ("video", "🎬")
    assert infer_creative_type("v2_aksiya_rolik") == ("video", "🎬")
    assert infer_creative_type("P1 | DENTIST") == ("photo", "🖼")
    assert infer_creative_type("photo_clinic_banner") == ("photo", "🖼")
    assert infer_creative_type("karusel_5_rasm") == ("carousel", "📑")
    assert infer_creative_type("unknown_ad") == ("creative", "🎬")


def test_resolve_ad_creative_known_id():
    details = resolve_ad_creative("120249419742870032")
    assert isinstance(details, AdCreativeDetails)
    assert details.creative_url == "https://www.instagram.com/p/DdMgcrcgnuH/"
    assert details.creative_type == "video"
    assert details.type_icon == "🎬"


def test_resolve_ad_creative_fallback():
    details = resolve_ad_creative("999999999999999999", ad_name="P99 | Test Banner")
    assert details.ad_id == "999999999999999999"
    assert details.creative_type == "photo"
    assert details.type_icon == "🖼"
    assert "999999999999999999" in details.creative_url


def test_save_and_get_stored_creative(tmp_path):
    save_creative(
        ad_id="test_ad_123",
        ad_name="V10 - Yangi Reel",
        creative_url="https://www.instagram.com/reel/test12345/",
        creative_type="video",
        type_icon="🎬",
    )
    loaded = get_stored_creative("test_ad_123")
    assert loaded is not None
    assert loaded.ad_name == "V10 - Yangi Reel"
    assert loaded.creative_url == "https://www.instagram.com/reel/test12345/"
    assert loaded.type_icon == "🎬"


def test_extract_lead_custom_fields_with_creative():
    fields = {"brend_nomi": "Test Brand"}
    cfs = extract_lead_custom_fields(
        fields,
        leadgen_id="123456789",
        creative_url="https://www.instagram.com/reel/DdVkUMngJiW/",
        creative_name="V6 - Brending",
        ad_id="120249953969790032",
    )
    cf_map = {f["field_id"]: f["values"][0]["value"] for f in cfs if "value" in f["values"][0]}

    assert cf_map.get(FIELD_CREATIVE_URL) == "https://www.instagram.com/reel/DdVkUMngJiW/"
    assert cf_map.get(FIELD_CREATIVE_NAME) == "V6 - Brending"
    assert cf_map.get(FIELD_UTM_CONTENT) == "V6 - Brending"
    assert cf_map.get(FIELD_OPENSTAT_AD) == "120249953969790032"


def test_build_leadgen_note_includes_creative():
    note = build_leadgen_note(
        leadgen_id="998877",
        payload={"ad_id": "120249953969790032"},
        fields={},
        ad_name="V6 - Brending",
        creative_url="https://www.instagram.com/reel/DdVkUMngJiW/",
        creative_type="video",
    )
    assert "REKLAMA KREATIVI (1-CLICK)" in note
    assert "https://www.instagram.com/reel/DdVkUMngJiW/" in note
    assert "V6 - Brending" in note


def test_build_telegram_message_includes_creative():
    msg = build_telegram_message(
        leadgen_id="998877",
        lead_id=53881373,
        name="Alisher",
        phone="+998901234567",
        email="",
        fields={},
        ad_name="V6 - Brending",
        creative_url="https://www.instagram.com/reel/DdVkUMngJiW/",
        creative_type="video",
    )
    assert "Kreativ:" in msg
    assert "https://www.instagram.com/reel/DdVkUMngJiW/" in msg
    assert "V6 - Brending" in msg
