"""Tests for AmoPipelineResolver."""
import pytest
from unittest.mock import MagicMock, patch

from src.services.core.crm.amocrm_resolver import (
    AmoPipelineResolver,
    PipelineMeta,
    StatusMeta,
    CustomFieldMeta,
    _norm,
)


def test_norm_helper():
    assert _norm("  Sotuv Bo'limi  ") == "sotuv bolimi"
    assert _norm("Qayta aloqa / Bog'lanish") == "qayta aloqa  boglanish"
    assert _norm("Avans summasi ($)") == "avans summasi "


def test_static_fallback():
    resolver = AmoPipelineResolver(amocrm=None)
    resolver._apply_static_fallbacks()

    assert resolver.get_pipeline_id("sotuv") == 11162698
    assert resolver.get_pipeline_id("main") == 11162698
    assert resolver.get_pipeline_id("farmer") == 10123318
    assert resolver.get_pipeline_id("reactivation") == 10947042
    assert resolver.get_pipeline_id("non_existent") is None


def test_status_resolution():
    resolver = AmoPipelineResolver(amocrm=None)
    pipe = PipelineMeta(id=11162698, name="Sotuv Bo'limi", is_main=True, is_archive=False)
    s1 = StatusMeta(id=89067962, name="Yangi LEads", sort=20, pipeline_id=11162698)
    s2 = StatusMeta(id=87609518, name="Qayta aloqa", sort=30, pipeline_id=11162698)
    s3 = StatusMeta(id=87609522, name="Kvalifikatsiya", sort=40, pipeline_id=11162698)

    pipe.statuses[89067962] = s1
    pipe.status_by_name[_norm("Yangi LEads")] = s1
    pipe.statuses[87609518] = s2
    pipe.status_by_name[_norm("Qayta aloqa")] = s2
    pipe.statuses[87609522] = s3
    pipe.status_by_name[_norm("Kvalifikatsiya")] = s3

    resolver._pipelines[11162698] = pipe
    resolver._pipeline_by_name["sotuv"] = pipe

    assert resolver.get_status_id("sotuv", "Yangi LEads") == 89067962
    assert resolver.get_status_id("sotuv", "yangi") == 89067962
    assert resolver.get_status_id("sotuv", "qayta aloqa") == 87609518
    assert resolver.get_status_id("sotuv", "kvalifikatsiya") == 87609522
    assert resolver.get_status_id("sotuv", "won") == 142
    assert resolver.get_status_id("sotuv", "lost") == 143


def test_custom_field_and_enum_resolution():
    resolver = AmoPipelineResolver(amocrm=None)
    cf = CustomFieldMeta(
        id=1034673,
        name="Faoliyat sohasi",
        field_type="select",
        enums={
            _norm("Ta’lim"): 12345,
            _norm("Ishlab chiqarish"): 67890,
            _norm("Savdo"): 11111,
        },
    )
    resolver._custom_fields[1034673] = cf
    resolver._custom_field_by_name[_norm("Faoliyat sohasi")] = cf

    assert resolver.get_custom_field_id("Faoliyat sohasi") == 1034673
    assert resolver.get_custom_field_id("faoliyat") == 1034673
    assert resolver.get_custom_field_enum_id("Faoliyat sohasi", "Ta’lim") == 12345
    assert resolver.get_custom_field_enum_id("Faoliyat sohasi", "Ishlab chiqarish") == 67890
    assert resolver.get_custom_field_enum_id("Faoliyat sohasi", "Mavjud emas") is None


def test_load_sync_mocked():
    mock_amo = MagicMock()
    mock_amo.base_url = "https://test.amocrm.ru"
    mock_amo._get_headers.return_value = {"Authorization": "Bearer test"}

    pipelines_payload = {
        "_embedded": {
            "pipelines": [
                {
                    "id": 100,
                    "name": "Test Pipeline",
                    "is_main": True,
                    "is_archive": False,
                    "_embedded": {
                        "statuses": [
                            {"id": 201, "name": "Stage 1", "sort": 10},
                            {"id": 202, "name": "Stage 2", "sort": 20},
                        ]
                    },
                }
            ]
        }
    }
    cf_payload = {
        "_embedded": {
            "custom_fields": [
                {"id": 501, "name": "Brand Name", "type": "text", "enums": []}
            ]
        }
    }

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "pipelines" in url:
            resp.json.return_value = pipelines_payload
        elif "custom_fields" in url:
            resp.json.return_value = cf_payload
        return resp

    with patch("requests.get", side_effect=mock_get):
        resolver = AmoPipelineResolver(amocrm=mock_amo)
        ok = resolver.load_sync(force=True)
        assert ok is True
        assert resolver.get_pipeline_id("Test Pipeline") == 100
        assert resolver.get_status_id(100, "Stage 1") == 201
        assert resolver.get_status_id(100, "Stage 2") == 202
        assert resolver.get_custom_field_id("Brand Name") == 501
