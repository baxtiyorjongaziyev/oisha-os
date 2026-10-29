from src.services.response_quality.staff_checkin import render


def test_unavailable_and_partial_are_not_zero():
    assert render(None) is None
    assert render({'total': 4}) is None


def test_inconsistent_counts_are_blocked():
    assert render({'total': 1, 'answered': 2, 'solid': 1}) is None


def test_old_context_and_unverified_transcripts_cannot_enter_message():
    text = render({'total': 3, 'answered': 2, 'solid': 1,
                   'last_checkin': 'Shaxboz aka bilan qayta gaplasha oldingizmi? ' * 20,
                   'summaries': ['Bonus va tolov kelishildi']})
    assert text
    assert 'Shaxboz' not in text
    assert 'Bonus' not in text
    assert '3 ta urinish' in text
