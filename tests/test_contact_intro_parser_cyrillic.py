from src.services.core.contact_intro_parser import parse_contact_intro


def test_cyrillic_labels():
    c = parse_contact_intro(
        "Исм: Али\nФамилия: Валиев\nТелефон: +998 90 123 45 67\n"
        "Компания: Nur\nҲудуд: Тошкент"
    )
    assert (c.first_name, c.last_name, c.phone, c.brand, c.region) == (
        "Али", "Валиев", "+998901234567", "Nur", "Тошкент",
    )


def test_isim_variant():
    c = parse_contact_intro(
        "Isim: Ali\nFamilya: Valiyev\nTelefon: 901234567\n"
        "Kompaniya: Nur\nHudud: Toshkent"
    )
    assert c.first_name == "Ali" and c.last_name == "Valiyev"


def test_cyrillic_region_activity():
    c = parse_contact_intro(
        "Имя: Ali\nҲудуд: Toshkent\nФаолият: Savdo\nТел: +998901234567"
    )
    assert (c.region, c.activity) == ("Toshkent", "Savdo")
