from datetime import datetime

from src.services.core.customer_outbound_policy import (
    automatic_customer_send_allowed,
    build_humanized_juma_greeting,
)


def test_only_juma_is_allowed_and_only_on_friday():
    friday = datetime(2026, 8, 14, 9, 0)
    thursday = datetime(2026, 8, 13, 9, 0)

    assert automatic_customer_send_allowed("juma", now=friday) is True
    assert automatic_customer_send_allowed("juma", now=thursday) is False
    assert automatic_customer_send_allowed("nps", now=friday) is False
    assert automatic_customer_send_allowed("auto_reply", now=friday) is False


def test_juma_greeting_is_natural_and_changes_each_week():
    first = build_humanized_juma_greeting("Akbarjon aka", datetime(2026, 8, 14))
    second = build_humanized_juma_greeting("Akbarjon aka", datetime(2026, 8, 21))

    assert first != second
    assert first.startswith("Assalomu alaykum.")
    assert "Akbarjon" not in first
    assert "aka" not in first.lower()
    assert "Juma" in first
    assert "AI" not in first
    assert "Jon Branding jamoasi" not in first
    assert len(first) < 280
