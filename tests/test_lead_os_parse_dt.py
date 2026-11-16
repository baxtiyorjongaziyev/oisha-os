"""LeadOperatingSystem._parse_dt must return comparable (aware) datetimes.

Regression: `last_client_message_at` is stored naive while
`lifecycle_updated_at` is timezone-aware, which made BackgroundMonitor fail
every cycle with "can't compare offset-naive and offset-aware datetimes".
"""
import datetime

from src.services.core.leads.lead_operating_system import LeadOperatingSystem


def test_naive_and_aware_values_are_comparable():
    naive = LeadOperatingSystem._parse_dt("2026-11-10T10:15:36.123456")
    aware = LeadOperatingSystem._parse_dt("2026-11-10T14:15:36+05:00")

    assert naive.tzinfo is not None
    assert aware.tzinfo is not None
    assert isinstance(naive < aware, bool)


def test_naive_value_is_read_as_server_local_time():
    raw = datetime.datetime(2026, 11, 10, 10, 15, 36)
    parsed = LeadOperatingSystem._parse_dt(raw.isoformat())

    assert parsed == raw.astimezone()


def test_aware_value_keeps_its_offset():
    parsed = LeadOperatingSystem._parse_dt("2026-11-10T09:00:00Z")

    assert parsed == datetime.datetime(2026, 11, 10, 9, 0, tzinfo=datetime.timezone.utc)


def test_empty_and_invalid_values_return_none():
    assert LeadOperatingSystem._parse_dt(None) is None
    assert LeadOperatingSystem._parse_dt("") is None
    assert LeadOperatingSystem._parse_dt("not-a-date") is None
