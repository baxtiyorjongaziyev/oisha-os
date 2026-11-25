from src.services.call_analytics.helpers import _apply_recruitment_override


def test_headhunter_candidate_becomes_jamoa():
    summary = (
        "Mijoz Headhunter orqali ariza qoldirgani uchun menejer bogʻlandi. "
        "Biroq mijoz hozir bandligini aytdi."
    )
    assert _apply_recruitment_override("Mijoz", summary, "") == "Jamoa"


def test_vacancy_and_resume_keywords():
    assert _apply_recruitment_override("Mijoz", "vakansiya böyicha") == "Jamoa"
    assert _apply_recruitment_override("Mijoz", "", "rezyume yubordim") == "Jamoa"
    assert _apply_recruitment_override("Mijoz", "hh.uz dan") == "Jamoa"


def test_real_sales_call_untouched():
    text = "Logotip va brending narxi haqida gaplashdik, taklif yuboramiz."
    assert _apply_recruitment_override("Mijoz", text) == "Mijoz"


def test_non_client_category_untouched():
    assert _apply_recruitment_override("Oila", "vakansiya") == "Oila"
