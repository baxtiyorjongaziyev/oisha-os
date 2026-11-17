import time

from src.services.core.crm.tag_payment_ranker import (
    format_ranking,
    lead_has_tag,
    rank_leads_by_payment_proximity,
)

NOW = time.time()


def _lead(lid, status_id, tags=("Shahnoza",), price=0, days=1):
    return {
        "id": lid,
        "name": f"Lead {lid}",
        "status_id": status_id,
        "price": price,
        "updated_at": int(NOW - days * 86400),
        "_embedded": {"tags": [{"name": t} for t in tags]},
    }


def test_tag_match_is_case_insensitive():
    assert lead_has_tag(_lead(1, 88871066, tags=("shahnoza",)), "Shahnoza")
    assert not lead_has_tag(_lead(1, 88871066, tags=("Oydin",)), "Shahnoza")


def test_payment_stage_ranks_first_and_closed_or_paid_excluded():
    leads = [
        _lead(1, 89067962),  # yangi murojaat
        _lead(2, 88871066),  # shartnoma va toʼlov
        _lead(3, 87609526),  # uchrashuv
        _lead(4, 142),  # sotuv (yopilgan)
        _lead(5, 86306518),  # toʼlov olingan
        _lead(6, 88871066, tags=("Oydin",)),  # boshqa teg
    ]
    ranked = rank_leads_by_payment_proximity(leads, "Shahnoza", now=NOW)
    assert [r.lead_id for r in ranked] == [2, 3, 1]


def test_stale_lead_scores_lower_than_fresh_same_stage():
    leads = [_lead(1, 88871066, days=30), _lead(2, 88871066, days=1)]
    ranked = rank_leads_by_payment_proximity(leads, "Shahnoza", now=NOW)
    assert [r.lead_id for r in ranked] == [2, 1]


def test_format_empty_and_limit():
    assert "topilmadi" in format_ranking("Shahnoza", [])
    leads = [_lead(i, 88871066) for i in range(1, 6)]
    assert len(rank_leads_by_payment_proximity(leads, "Shahnoza", limit=2, now=NOW)) == 2
