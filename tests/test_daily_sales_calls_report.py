"""
Tests for daily_sales_calls_report.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.daily_sales_calls_report import (
    _format_duration,
    _normalize_phone,
    _resolve_rep_name,
    build_report,
    fetch_calls,
)


# ── _format_duration tests ──────────────────────────────────────
class TestFormatDuration:
    def test_zero(self):
        assert _format_duration(0) == "0s"

    def test_seconds_only(self):
        assert _format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        result = _format_duration(125)
        assert "2d" in result
        assert "5s" in result

    def test_hours(self):
        result = _format_duration(3661)
        assert "1s" in result  # 1 soat
        assert "1d" in result  # 1 daqiqa


# ── _normalize_phone tests ──────────────────────────────────────
class TestNormalizePhone:
    def test_clean_number(self):
        assert _normalize_phone("+998 (90) 123-45-67") == "998901234567"

    def test_empty(self):
        assert _normalize_phone("") == ""
        assert _normalize_phone(None) == ""


# ── build_report tests ──────────────────────────────────────────
class TestBuildReport:
    def test_empty_calls(self):
        report = build_report([], "2026-09-28")
        assert "topilmadi" in report
        assert "2026-09-28" in report

    def test_basic_report(self):
        calls = [
            {
                "direction": 0,
                "src_number": "",
                "client_number": "+998951112233",
                "duration": 120,
                "answered": 1,
                "src_id": 24,
            },
            {
                "direction": 1,
                "src_number": "",
                "client_number": "+998951112233",
                "duration": 60,
                "answered": 1,
                "src_id": 24,
            },
            {
                "direction": 0,
                "src_number": "",
                "client_number": "+998952223344",
                "duration": 0,
                "answered": 0,
                "src_id": 24,
            },
        ]
        report = build_report(calls, "2026-09-28")
        assert "Jami" in report
        assert "2026-09-28" in report
        # 3 ta qo'ng'iroq, 2 tasi javob
        assert "*3*" in report

    def test_multiple_reps(self):
        calls = [
            {
                "direction": 0,
                "src_number": "998901111111",
                "client_number": "+998952222222",
                "duration": 300,
                "answered": 1,
                "src_id": 10,
            },
            {
                "direction": 0,
                "src_number": "998903333333",
                "client_number": "+998954444444",
                "duration": 200,
                "answered": 1,
                "src_id": 20,
            },
        ]
        report = build_report(calls, "2026-09-28")
        # Ikki xil sotuvchi
        assert "998901111111" in report or "998903333333" in report


# ── fetch_calls tests ───────────────────────────────────────────
class TestFetchCalls:
    @patch("requests.post")
    def test_successful_fetch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"direction": 0, "client_number": "+998901234567", "duration": 120, "answered": 1, "src_id": 24, "start_time": 1500},
                {"direction": 1, "client_number": "+998901234567", "duration": 60, "answered": 1, "src_id": 24, "start_time": 1600},
            ],
            "results_count": 2,
            "results_remains": 0,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        calls = fetch_calls("test_api_key", "test.moizvonki.ru", 1000, 2000)
        assert len(calls) == 2
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_api_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("Connection error")

        calls = fetch_calls("test_api_key", "test.moizvonki.ru", 1000, 2000)
        assert calls == []

    @patch("requests.post")
    def test_empty_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [],
            "results_count": 0,
            "results_remains": 0,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        calls = fetch_calls("test_api_key", "test.moizvonki.ru", 1000, 2000)
        assert calls == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
