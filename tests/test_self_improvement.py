"""Tests for SelfImprovementAgent pure logic (no LLM / DB required)."""
import json

from src.services.core.self_improvement_agent import SelfImprovementAgent


def _valid_item(**overrides):
    item = {
        "area": "lead followup",
        "gap": "48 soatdan ortiq javobsiz leadlar to'planmoqda",
        "proposal": "FollowupAgent qo'shish kerak",
        "ai_agent_help": "Yangi agent avtomatik eslatma yuboradi",
        "priority": "high",
        "impact": "Lead yo'qotish kamayadi",
    }
    item.update(overrides)
    return item


class TestParseProposals:
    def test_plain_json_array(self):
        text = json.dumps([_valid_item()])
        result = SelfImprovementAgent._parse_proposals(text)
        assert len(result) == 1
        assert result[0]["area"] == "lead followup"
        assert result[0]["priority"] == "high"

    def test_fenced_json(self):
        text = "```json\n" + json.dumps([_valid_item()]) + "\n```"
        result = SelfImprovementAgent._parse_proposals(text)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        assert SelfImprovementAgent._parse_proposals("not json at all") == []

    def test_empty_and_none_like(self):
        assert SelfImprovementAgent._parse_proposals("") == []
        assert SelfImprovementAgent._parse_proposals("[]") == []

    def test_non_list_returns_empty(self):
        assert SelfImprovementAgent._parse_proposals('{"area": "x"}') == []

    def test_missing_required_fields_skipped(self):
        items = [_valid_item(), {"area": "x"}, "garbage"]
        result = SelfImprovementAgent._parse_proposals(json.dumps(items))
        assert len(result) == 1

    def test_invalid_priority_defaults_to_medium(self):
        result = SelfImprovementAgent._parse_proposals(
            json.dumps([_valid_item(priority="urgent!!")])
        )
        assert result[0]["priority"] == "medium"

    def test_capped_at_five(self):
        items = [_valid_item(area=f"area-{i}") for i in range(10)]
        result = SelfImprovementAgent._parse_proposals(json.dumps(items))
        assert len(result) == 5

    def test_long_fields_truncated(self):
        result = SelfImprovementAgent._parse_proposals(
            json.dumps([_valid_item(gap="x" * 2000)])
        )
        assert len(result[0]["gap"]) == 500


class TestMeaningfulSignals:
    def test_only_timestamp_is_not_meaningful(self):
        assert not SelfImprovementAgent._has_meaningful_signals(
            {"collected_at": "2026-07-15"}
        )

    def test_none_and_empty_values_not_meaningful(self):
        signals = {
            "collected_at": "2026-07-15",
            "failed_actions": [],
            "retry_queue_depth": 0,
            "avg_response_quality": None,
        }
        assert not SelfImprovementAgent._has_meaningful_signals(signals)

    def test_nonzero_count_is_meaningful(self):
        assert SelfImprovementAgent._has_meaningful_signals(
            {"collected_at": "2026-07-15", "retry_queue_depth": 7}
        )

    def test_nonempty_list_is_meaningful(self):
        assert SelfImprovementAgent._has_meaningful_signals(
            {"collected_at": "2026-07-15", "failed_actions": [{"action": "send", "failures": 3}]}
        )


class TestFormatReport:
    def test_empty_returns_empty_string(self):
        assert SelfImprovementAgent.format_report([]) == ""

    def test_report_contains_core_fields(self):
        report = SelfImprovementAgent.format_report([_valid_item()])
        assert "LEAD FOLLOWUP" in report
        assert "FollowupAgent qo'shish kerak" in report
        assert "🔴" in report
        assert "/improve_approve" in report

    def test_report_without_optional_fields(self):
        item = _valid_item(ai_agent_help="", impact="")
        report = SelfImprovementAgent.format_report([item])
        assert "AI yordam" not in report
        assert "Natija:" not in report
