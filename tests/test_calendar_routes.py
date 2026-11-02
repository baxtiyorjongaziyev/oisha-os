from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from src.services.api_server.core import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "test_secret_key_1234567890")
    return TestClient(app)


def test_calendar_routes_unauthorized(client):
    response = client.get("/api/calendar/events")
    assert response.status_code == 401


def test_calendar_routes_list_events(client, monkeypatch):
    with patch("src.api.routes.calendar_routes.GoogleCalendarSync") as mock_sync_cls:
        mock_sync = MagicMock()
        mock_sync.service = MagicMock()
        mock_sync.calendar_id = "test@gmail.com"
        mock_sync.get_upcoming_events.return_value = [
            {
                "id": "evt1",
                "summary": "Mijoz bilan qo'ng'iroq",
                "start": {"dateTime": "2026-11-03T10:00:00+05:00"},
                "end": {"dateTime": "2026-11-03T11:00:00+05:00"},
                "htmlLink": "https://calendar.google.com/event?eid=1",
                "status": "confirmed",
            }
        ]
        mock_sync_cls.return_value = mock_sync

        headers = {"Authorization": "Bearer test_secret_key_1234567890"}
        response = client.get("/api/calendar/events?date=2026-11-03", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 1
        assert data["events"][0]["summary"] == "Mijoz bilan qo'ng'iroq"


def test_calendar_routes_create_event(client, monkeypatch):
    with patch("src.api.routes.calendar_routes.GoogleCalendarSync") as mock_sync_cls:
        mock_sync = MagicMock()
        mock_sync.service = MagicMock()
        mock_sync.calendar_id = "test@gmail.com"
        mock_sync.create_event.return_value = {
            "id": "new_evt_123",
            "htmlLink": "https://calendar.google.com/event?eid=new",
            "summary": "Yangi uchrashuv",
        }
        mock_sync_cls.return_value = mock_sync

        headers = {"Authorization": "Bearer test_secret_key_1234567890"}
        payload = {
            "summary": "Yangi uchrashuv",
            "start_time": "2026-11-03T15:00:00+05:00",
            "end_time": "2026-11-03T16:00:00+05:00",
            "description": "Kelishuv muhokamasi",
        }
        response = client.post("/api/calendar/events", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["event_id"] == "new_evt_123"
        assert data["html_link"] == "https://calendar.google.com/event?eid=new"


def test_calendar_routes_free_slots(client, monkeypatch):
    with patch("src.api.routes.calendar_routes.GoogleCalendarSync") as mock_sync_cls:
        mock_sync = MagicMock()
        mock_sync.service = MagicMock()
        mock_sync.calendar_id = "test@gmail.com"
        mock_sync.get_free_slots.return_value = [
            {"start": "11:00", "end": "12:00"},
            {"start": "14:00", "end": "15:00"},
        ]
        mock_sync_cls.return_value = mock_sync

        headers = {"Authorization": "Bearer test_secret_key_1234567890"}
        response = client.get("/api/calendar/free-slots?date=2026-11-03", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["free_slots"]) == 2
