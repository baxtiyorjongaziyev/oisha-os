from src.services.response_quality.checkin_gate import evaluate


def test_reported_repetition_is_blocked():
    assert not evaluate("Shaxboz aka bilan qayta gaplasha oldingizmi? " * 5).allowed


def test_internal_markdown_is_blocked():
    assert not evaluate("Mumtozmaxal, ```markdown\n# Mening xabarim\nSalom, natijani yozing.").allowed


def test_fabricated_dialogue_is_blocked():
    assert not evaluate('Qo‘ng‘iroq: "Salom". Javob: "Yo‘q".').allowed


def test_unapproved_offer_is_blocked():
    assert not evaluate("Mijozga kichik bonus taqdim etib ko‘raylikmi?").allowed


def test_neutral_respectful_question_is_allowed():
    assert evaluate("Keyingi qadamni kelishishda yordam kerakmi? Natijani shu xabarga javoban yozishingiz mumkin.").allowed
