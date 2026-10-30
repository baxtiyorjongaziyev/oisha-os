from scripts.check_uzbek_text import find_violations, is_allowed_word


def test_flags_uzbek_apostrophe():
    found = find_violations('matn = "qo\'ng\'iroq"')

    assert found
    assert found[0][1] == "qo'ng'iroq"


def test_flags_tutuq_typed_with_ascii():
    found = find_violations('matn = "ma\'no"')

    assert found
    assert found[0][1] == "ma'no"


def test_allows_english_contractions():
    for text in ("don't", "we're", "I've", "he'll", "John's", "o'clock"):
        assert find_violations(f'matn = "{text}"') == [], text


def test_allows_new_alphabet():
    assert find_violations('matn = "qönğiroq"') == []
    assert find_violations('matn = "ğalaba"') == []
    assert find_violations('matn = "şahar"') == []


def test_allows_tutuq_mark():
    assert find_violations('matn = "maʼno"') == []
    assert find_violations('matn = "eʼlon"') == []


def test_ignores_string_delimiters():
    assert find_violations("x = 'a' + 'b'") == []


def test_english_suffix_helper():
    assert is_allowed_word("John's") is True
    assert is_allowed_word("qo'ng'iroq") is False
