from src.handlers.group_mention import is_name_called, is_team_chat, strip_call


def test_name_variants_detected():
    for t in ["oisha shu yerdamisan?", "Oyisha, narx?", "Оиша қаерда", "ойша!", "salom Oisha", "oishaga ayt"]:
        assert is_name_called(t), t


def test_username_tag_detected():
    assert is_name_called("@jonairobot holat?", "jonairobot")
    assert is_name_called("@JonAIRobot holat?", "@jonairobot")


def test_unrelated_text_ignored():
    for t in ["", "salom hammaga", "poisha", "bugun yig'ilish bor"]:
        assert not is_name_called(t, "jonairobot"), t


def test_strip_call():
    assert strip_call("Oisha, bugungi lidlar?") == "bugungi lidlar?"
    assert strip_call("@jonairobot holat", "jonairobot") == "holat"
    assert strip_call("Bugun oisha nima qildi?") == "Bugun oisha nima qildi?"


def test_team_chat_detection():
    assert is_team_chat(1, "Jon Branding Team", set())
    assert is_team_chat(1, "Loyihalar | Jon.Branding", set())
    assert is_team_chat(5, "Boshqa", {5})
    assert not is_team_chat(1, "Mijozlar guruhi", set())
