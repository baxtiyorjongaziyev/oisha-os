from src.services.core.gcalendar import GoogleCalendarSync, _stringify_private


class _Execute:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class _Events:
    def __init__(self):
        self.calls = []
        self.insert_results = []
        self.delete_error = None

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        if self.insert_results:
            result = self.insert_results.pop(0)
            if isinstance(result, Exception):
                return _Execute(error=result)
            return _Execute(result=result)
        return _Execute(result={"id": "evt-1", "htmlLink": "https://cal/evt-1"})

    def patch(self, **kwargs):
        self.calls.append(("patch", kwargs))
        return _Execute(result={"id": kwargs.get("eventId")})

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return _Execute(error=self.delete_error)


class _Service:
    def __init__(self):
        self._events = _Events()

    def events(self):
        return self._events


def _sync():
    sync = GoogleCalendarSync.__new__(GoogleCalendarSync)
    sync.calendar_id = "team@example.com"
    sync.service = _Service()
    return sync


def test_credentials_path_env_overrides_constructor(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/srv/secrets/calendar.json")
    monkeypatch.setattr(GoogleCalendarSync, "_authenticate", lambda self: None)

    sync = GoogleCalendarSync("data/creds.json")

    assert sync.credentials_path == "/srv/secrets/calendar.json"


def test_credentials_path_falls_back_to_constructor(monkeypatch):
    monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", raising=False)
    monkeypatch.setattr(GoogleCalendarSync, "_authenticate", lambda self: None)

    sync = GoogleCalendarSync("data/creds.json")

    assert sync.credentials_path == "data/creds.json"


def test_create_event_returns_event_and_uses_configured_calendar():
    sync = _sync()

    event = sync.create_event(
        summary="Ozodbek - Brending",
        start_time="2026-05-14T13:00:00+05:00",
        end_time="2026-05-14T14:00:00+05:00",
        description="Oisha Telegram suhbatidan yaratdi.",
        location="U Enter",
        extended_properties={"telegram_chat_id": 9001, "participant": "Ozodbek"},
    )

    assert event["id"] == "evt-1"
    method, call = sync.service._events.calls[0]
    assert method == "insert"
    assert call["calendarId"] == "team@example.com"
    assert call["body"]["summary"] == "Ozodbek - Brending"
    assert call["body"]["start"]["timeZone"] == "Asia/Tashkent"
    assert call["body"]["extendedProperties"]["private"] == {
        "telegram_chat_id": "9001",
        "participant": "Ozodbek",
    }


def test_create_event_retries_without_meet_link_when_conference_rejected():
    sync = _sync()
    sync.service._events.insert_results = [
        RuntimeError("Invalid conference type value"),
        {"id": "evt-2"},
    ]

    event = sync.create_event(
        summary="Ozodbek - Uchrashuv",
        start_time="2026-05-14T13:00:00+05:00",
        end_time="2026-05-14T14:00:00+05:00",
    )

    assert event["id"] == "evt-2"
    first = sync.service._events.calls[0][1]
    second = sync.service._events.calls[1][1]
    assert "conferenceData" in first["body"]
    assert "conferenceData" not in second["body"]
    assert "conferenceDataVersion" not in second


def test_delete_event_is_idempotent_for_missing_event():
    sync = _sync()
    sync.service._events.delete_error = RuntimeError("HttpError 404: Not Found")

    assert sync.delete_event("evt-404") is True
    method, call = sync.service._events.calls[0]
    assert method == "delete"
    assert call["calendarId"] == "team@example.com"
    assert call["eventId"] == "evt-404"


def test_delete_event_returns_false_on_other_errors():
    sync = _sync()
    sync.service._events.delete_error = RuntimeError("backend error")

    assert sync.delete_event("evt-1") is False


def test_update_event_patches_only_given_fields():
    sync = _sync()

    event = sync.update_event(
        "evt-1",
        start_time="2026-05-14T15:00:00+05:00",
        end_time="2026-05-14T16:00:00+05:00",
    )

    assert event["id"] == "evt-1"
    method, call = sync.service._events.calls[0]
    assert method == "patch"
    assert call["body"] == {
        "start": {"dateTime": "2026-05-14T15:00:00+05:00", "timeZone": "Asia/Tashkent"},
        "end": {"dateTime": "2026-05-14T16:00:00+05:00", "timeZone": "Asia/Tashkent"},
    }


def test_update_event_without_changes_returns_none():
    sync = _sync()

    assert sync.update_event("evt-1") is None
    assert sync.service._events.calls == []


def test_stringify_private_drops_empty_values():
    assert _stringify_private({"a": 1, "b": "", "c": None}) == {"a": "1"}
