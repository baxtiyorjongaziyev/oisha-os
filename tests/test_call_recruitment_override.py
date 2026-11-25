from src.services.call_analytics.recruitment import apply_recruitment_override


def test_headhunter_candidate_becomes_jamoa():
    summary = (
        "Mijoz Headhunter orqali ariza qoldirgani uchun menejer bogʻlandi. "
        "Biroq mijoz hozir bandligini aytdi."
    )
    assert apply_recruitment_override("Mijoz", summary) == "Jamoa"


def test_vacancy_and_resume_keywords():
    assert apply_recruitment_override("Mijoz", "vakansiya böyicha") == "Jamoa"
    assert apply_recruitment_override("Mijoz", "rezyume yubordi") == "Jamoa"
    assert apply_recruitment_override("Mijoz", "hh.uz dan ariza") == "Jamoa"


def test_real_sales_call_untouched():
    text = "Logotip va brending narxi haqida gaplashdik, taklif yuboramiz."
    assert apply_recruitment_override("Mijoz", text) == "Mijoz"


def test_price_discount_offer_untouched():
    assert apply_recruitment_override("Mijoz", "Narx tushirish taklifi berildi") == "Mijoz"


def test_non_client_category_untouched():
    assert apply_recruitment_override("Oila", "vakansiya") == "Oila"
