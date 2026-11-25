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


class _FakeAmo:
    def __init__(self, pipeline_id):
        self.pipeline_id = pipeline_id
        self.moved = None

    async def get_lead(self, lead_id):
        return {"id": lead_id, "pipeline_id": self.pipeline_id}

    async def update_lead_status(self, lead_id, status_id, pipeline_id=None):
        self.moved = (lead_id, status_id, pipeline_id)
        return True


def test_candidate_moved_to_hr_pipeline():
    import asyncio
    from src.services.call_analytics.recruitment import (
        HR_SCREENING_STATUS_ID, move_candidate_to_hr,
    )
    from src.services.core.crm.amocrm_pipeline_config import HR_PIPELINE_ID

    amo = _FakeAmo(pipeline_id=11162698)
    assert asyncio.run(move_candidate_to_hr(amo, 54859035, {"hr_nomzod": True}))
    assert amo.moved == (54859035, HR_SCREENING_STATUS_ID, HR_PIPELINE_ID)


def test_already_in_hr_or_not_candidate_untouched():
    import asyncio
    from src.services.call_analytics.recruitment import move_candidate_to_hr
    from src.services.core.crm.amocrm_pipeline_config import HR_PIPELINE_ID

    amo = _FakeAmo(pipeline_id=HR_PIPELINE_ID)
    assert not asyncio.run(move_candidate_to_hr(amo, 1, {"hr_nomzod": True}))
    amo2 = _FakeAmo(pipeline_id=1)
    assert not asyncio.run(move_candidate_to_hr(amo2, 1, {"hr_nomzod": False}))
    assert amo.moved is None and amo2.moved is None
