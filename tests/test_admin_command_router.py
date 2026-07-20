from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)


def test_chatid_response_includes_chat_and_topic_ids():
    response = build_chatid_response(
        chat_id=-100123,
        chat_title="Finance",
        topic_id=77,
    )

    assert response.parse_mode == "html"
    assert "<code>-100123</code>" in response.text
    assert "Finance" in response.text
    assert "<code>77</code>" in response.text


def test_chatid_response_guides_when_topic_is_missing():
    response = build_chatid_response(
        chat_id=150074828,
        chat_title="shaxsiy",
        topic_id=None,
    )

    assert "Topic ID olish uchun" in response.text
    assert "/chatid" in response.text


def test_start_role_owner_and_guest_resolution():
    assert resolve_start_role(
        sender_id=150074828,
        owner_id=1,
        get_role=lambda _sender_id: "MANAGER",
    ) == "OWNER"
    assert resolve_start_role(
        sender_id=42,
        owner_id=1,
        get_role=lambda _sender_id: None,
    ) == "GUEST"


def test_start_response_is_transport_independent():
    response = build_start_response(role_name="Owner", now_text="21.07.2026 09:00")

    assert "Oisha-OS Enterprise" in response.text
    assert "Owner" in response.text
    assert "21.07.2026 09:00" in response.text


def test_oisha_stats_response_formats_health_label():
    response = build_oisha_stats_response(
        stats={"leads_found": 3, "messages_synced": 12},
        health_score=49,
    )

    assert "BUSINESS PERFORMANCE" in response.text
    assert "`3` ta" in response.text
    assert "`12` ta" in response.text
    assert "`49%` (KRITIK HOLAT)" in response.text


def test_sales_priorities_response_formats_ranked_leads():
    response = build_sales_priorities_response(
        {
            "status": "ready",
            "source": "amocrm",
            "scanned_count": 3,
            "skipped_closed_count": 1,
            "items": [
                {
                    "lead_id": 123,
                    "name": "Oltin Savdo",
                    "priority": "high",
                    "priority_score": 75,
                    "reasons": ["no_open_task", "stale_48h_plus", "high_value"],
                    "action": "Create the next follow-up task after owner approval.",
                }
            ],
        }
    )

    assert "Bugun sotuvchi" in response.text
    assert "Oltin Savdo #123" in response.text
    assert "vazifa yo'q" in response.text
    assert "48+ soat jim" in response.text
    assert "Soxta fakt" in response.text


def test_sales_priorities_response_refuses_fake_source_unavailable():
    response = build_sales_priorities_response(
        {
            "status": "source_unavailable",
            "source": "amocrm",
            "reason": "amocrm_client_unavailable",
            "items": [],
        }
    )

    assert "tayyor emas" in response.text
    assert "Soxta lead" in response.text


def test_project_risks_response_formats_ranked_projects():
    response = build_project_risks_response(
        {
            "status": "ready",
            "source": "airtable",
            "scanned_count": 2,
            "skipped_closed_count": 0,
            "items": [
                {
                    "project_id": "rec1",
                    "name": "Brandbook",
                    "risk": "critical",
                    "risk_score": 80,
                    "reasons": ["overdue", "owner_missing"],
                    "action": "Bugun yangi deadline tasdiqlang.",
                    "evidence": {
                        "deadline": "2026-07-18",
                        "manager": "",
                    },
                }
            ],
        }
    )

    assert "Loyiha/deadline risklari" in response.text
    assert "Brandbook" in response.text
    assert "muddat o'tgan" in response.text
    assert "PM/mas'ul yo'q" in response.text
    assert "Soxta fakt" in response.text


def test_project_risks_response_refuses_fake_source_unavailable():
    response = build_project_risks_response(
        {
            "status": "source_unavailable",
            "source": "airtable",
            "reason": "airtable_client_unavailable",
            "items": [],
        }
    )

    assert "tayyor emas" in response.text
    assert "Soxta deadline" in response.text


def test_finance_risks_response_formats_ranked_projects():
    response = build_finance_risks_response(
        {
            "status": "ready",
            "source": "project_finance",
            "scanned_count": 1,
            "skipped_closed_count": 0,
            "items": [
                {
                    "project_id": "fin1",
                    "name": "Brandbook",
                    "risk": "critical",
                    "risk_score": 85,
                    "reasons": ["advance_below_50", "remaining_payment"],
                    "action": "50% avansni yoping.",
                    "evidence": {
                        "budget": 20_000_000,
                        "paid_amount": 2_000_000,
                        "remaining_amount": 18_000_000,
                    },
                }
            ],
        }
    )

    assert "Moliya/payment risklari" in response.text
    assert "Brandbook" in response.text
    assert "50% avans" in response.text
    assert "Qoldiq" in response.text
    assert "Marja taxmin qilinmadi" in response.text


def test_finance_risks_response_refuses_fake_source_unavailable():
    response = build_finance_risks_response(
        {
            "status": "source_unavailable",
            "source": "project_finance",
            "reason": "finance_source_unavailable",
            "items": [],
        }
    )

    assert "tayyor emas" in response.text
    assert "Soxta to'lov" in response.text


def test_team_capacity_response_formats_ranked_workload():
    response = build_team_capacity_response(
        {
            "status": "ready",
            "source": "project_assignments",
            "scanned_count": 2,
            "unassigned_project_count": 1,
            "items": [
                {
                    "owner_name": "Ali",
                    "load": "overloaded",
                    "load_score": 88,
                    "reasons": ["overdue_projects", "due_3_days"],
                    "action": "Qayta taqsimlang.",
                    "evidence": {
                        "active_projects": 5,
                        "overdue_projects": 1,
                        "due_3_days": 2,
                    },
                }
            ],
        }
    )

    assert "Jamoa yuklamasi" in response.text
    assert "Ali" in response.text
    assert "kechikkan loyiha" in response.text
    assert "Yuklama taxmin qilinmadi" in response.text


def test_team_capacity_response_refuses_fake_source_unavailable():
    response = build_team_capacity_response(
        {
            "status": "source_unavailable",
            "source": "project_assignments",
            "reason": "project_source_unavailable",
            "items": [],
        }
    )

    assert "tayyor emas" in response.text
    assert "Soxta bandlik" in response.text


def test_command_center_response_formats_section_summary():
    response = build_command_center_response(
        {
            "status": "attention_required",
            "summary": {
                "attention_items": 3,
                "ready_sections": 4,
                "total_sections": 4,
                "unavailable_sections": [],
            },
            "sections": {
                "sales": {"status": "ready", "items": [{"name": "Lead A", "priority": "high", "priority_score": 80}]},
                "projects": {"status": "ready", "items": [{"name": "Project A", "risk": "critical", "risk_score": 90}]},
                "finance": {"status": "empty", "items": []},
                "team": {"status": "ready", "items": [{"owner_name": "Ali", "load": "busy", "load_score": 45}]},
            },
        }
    )

    assert "Oisha Command Center" in response.text
    assert "Sotuv: Lead A" in response.text
    assert "Loyihalar: Project A" in response.text
    assert "Jamoa: Ali" in response.text
    assert "Soxta data" in response.text
