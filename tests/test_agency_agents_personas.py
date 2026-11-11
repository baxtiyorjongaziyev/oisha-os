"""msitarzewski/agency-agents dan olingan qoʻshimcha personalar va ularning routingi."""

import pytest

from src.agents.persona_router import PersonaRouter
from src.services.core.agency_personas import AGENCY_PERSONAS, GROWTH_PERSONAS


@pytest.mark.parametrize("key", sorted(GROWTH_PERSONAS))
def test_growth_personas_are_registered(key):
    assert AGENCY_PERSONAS[key] == GROWTH_PERSONAS[key]
    assert GROWTH_PERSONAS[key].startswith("You are ")


def test_every_routed_persona_is_defined():
    missing = {key for _, key in PersonaRouter.DOMAIN_MAP if key not in AGENCY_PERSONAS}
    assert not missing


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Kuchli offer va lid magnit kerak", "sales-offer-lead-gen-strategist"),
        ("CAPI va pixel dublikat event yuboryapti", "paid-media-tracking-specialist"),
        ("Targetolog uchun Meta Ads strukturasi", "paid-media-paid-social-strategist"),
        ("Yangi kreativ variantlari kerak", "paid-media-creative-strategist"),
        ("Instagram uchun karusel tayyorlang", "marketing-carousel-growth-engine"),
        ("Mijozlarga rassilka ketma-ketligi", "marketing-email-strategist"),
        ("Midjourney uchun rasm prompt yozing", "design-image-prompt-engineer"),
        ("Dizaynerlar orasida resurs taqsimoti", "project-management-studio-producer"),
        # Mavjud yoʻnalishlar buzilmagan
        ("Narx qancha?", "sales-deal-strategist"),
        ("Instagram reels gʻoyasi", "marketing-instagram-curator"),
        ("Logo va brendbuk kerak", "design-brand-guardian"),
        ("narx aytishga qoʻrqyapman", "sales-psychology-coach"),
    ],
)
def test_persona_routing(message, expected):
    assert PersonaRouter.route_key(message) == expected
