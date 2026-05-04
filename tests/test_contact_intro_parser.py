from src.services.core.contact_intro_parser import normalize_phone, parse_contact_intro


def test_parse_structured_uzbek_intro_post():
    text = "\n".join(
        [
            "\u2705Ism : Abdujalil",
            "\u2705Familiya : Rasulov",
            "\u2705Tug\u2019ilgan kun: 28.10.1990",
            "\u2705Tug\u2019ilgan joy: Tashkent",
            "\u2705Brend: SABAB MEBEL",
            "\u2705Faoliyat turi : Mebel xizmatlari",
            "\u2705Faoliyat hududi : \u0422oshkent",
            "\u2705Lavozim: Asoschi & Raxbar",
            "\u2705Tel: +998908203333",
            "\u2705Telegram : @Abdujalil_3333",
            "\u2705Instagram : @SABAB MEBEL",
            "      @SABABMEBEL",
        ]
    )

    intro = parse_contact_intro(text, source_chat='"TEZ NATIJA 5" UMUMIY')

    assert intro is not None
    assert intro.full_name == "Abdujalil Rasulov"
    assert intro.phone == "+998908203333"
    assert intro.telegram == "@Abdujalil_3333"
    assert "@SABABMEBEL" in intro.instagram
    assert intro.brand == "SABAB MEBEL"
    assert intro.activity == "Mebel xizmatlari"
    assert intro.group_label == "TEZ NATIJA"
    assert "Original post:" in intro.note


def test_parse_rejects_plain_message_with_phone():
    text = "Assalomu alaykum, mana telefonim +998901112233, keyin gaplashamiz."

    assert parse_contact_intro(text, source_chat="Some group") is None


def test_normalize_uzbek_phone_variants():
    assert normalize_phone("90 820 33 33") == "+998908203333"
    assert normalize_phone("+998 (90) 820-33-33") == "+998908203333"
