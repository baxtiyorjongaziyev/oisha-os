from unittest.mock import MagicMock, patch
import pytest
from src.services.core.gcalendar import GoogleCalendarSync


def test_gcalendar_init_default_calendar_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)
    with patch.object(GoogleCalendarSync, "_authenticate"):
        sync = GoogleCalendarSync(calendar_id="custom@gmail.com")
        assert sync.calendar_id == "custom@gmail.com"


def test_gcalendar_init_env_calendar_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "env_user@gmail.com")
    with patch.object(GoogleCalendarSync, "_authenticate"):
        sync = GoogleCalendarSync()
        assert sync.calendar_id == "env_user@gmail.com"


def test_gcalendar_create_event_uses_calendar_id():
    with patch.object(GoogleCalendarSync, "_authenticate"):
        sync = GoogleCalendarSync(calendar_id="mycal@gmail.com")
        sync.service = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = {"htmlLink": "https://calendar.google.com/event"}
        sync.service.events.return_value.insert.return_value = mock_insert

        res = sync.create_event(
            summary="Meeting",
            start_time="2026-11-02T10:00:00+05:00",
            end_time="2026-11-02T11:00:00+05:00",
        )
        assert res is True
        sync.service.events().insert.assert_called_once()
        call_kwargs = sync.service.events().insert.call_args[1]
        assert call_kwargs["calendarId"] == "mycal@gmail.com"


def test_gcalendar_get_upcoming_events_uses_calendar_id():
    with patch.object(GoogleCalendarSync, "_authenticate"):
        sync = GoogleCalendarSync(calendar_id="mycal@gmail.com")
        sync.service = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {"items": [{"id": "1", "summary": "Call"}]}
        sync.service.events.return_value.list.return_value = mock_list

        items = sync.get_upcoming_events(date_str="2026-11-02")
        assert len(items) == 1
        assert items[0]["summary"] == "Call"
        call_kwargs = sync.service.events().list.call_args[1]
        assert call_kwargs["calendarId"] == "mycal@gmail.com"
