from scripts.check_uzbek_text import (
    Violation,
    apply_baseline,
    find_violations,
    is_allowed_word,
    load_baseline,
    write_baseline,
)


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


def _violation(path: str, word: str, line: int = 1) -> Violation:
    return Violation(path=path, line=line, column=1, word=word)


def test_baseline_roundtrip_keeps_counts(tmp_path):
    baseline = tmp_path / "baseline.txt"
    violations = [
        _violation("src/a.py", "qo'ng'iroq"),
        _violation("src/a.py", "qo'ng'iroq"),
        _violation("src/b.py", "ma'no"),
    ]

    write_baseline(baseline, violations)
    counts = load_baseline(baseline)

    assert counts["src/a.py"] == 2
    assert counts["src/b.py"] == 1


def test_baseline_allows_existing_debt_only(tmp_path):
    baseline = tmp_path / "baseline.txt"
    write_baseline(baseline, [_violation("src/a.py", "qo'ng'iroq")])
    counts = load_baseline(baseline)

    existing = [_violation("src/a.py", "qo'ng'iroq")]
    extra = existing + [_violation("src/a.py", "qo'ng'iroq", line=5)]

    assert apply_baseline(existing, counts) == []
    assert [v.line for v in apply_baseline(extra, counts)] == [5]


def test_baseline_flags_new_file(tmp_path):
    baseline = tmp_path / "baseline.txt"
    write_baseline(baseline, [_violation("src/a.py", "qo'ng'iroq")])
    counts = load_baseline(baseline)

    fresh = apply_baseline([_violation("src/new.py", "ma'no")], counts)

    assert [v.path for v in fresh] == ["src/new.py"]


def test_missing_baseline_is_empty(tmp_path):
    assert load_baseline(tmp_path / "yo'q.txt") == {}
