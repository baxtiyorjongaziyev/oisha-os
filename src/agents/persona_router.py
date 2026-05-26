"""
PersonaRouter — Maps incoming message intent to the right agency persona.

Usage:
    from src.agents.persona_router import PersonaRouter

    ctx = PersonaRouter.route("logo va branding kerak", intent="pricing")
    # Returns "\n\n[AGENCY PERSONA: design-brand-guardian]\n..." or ""
"""

from __future__ import annotations

import re
from typing import Optional

from src.services.core.agency_personas import AGENCY_PERSONAS


class PersonaRouter:
    """Keyword/regex-based routing from message + intent → agency persona context block."""

    # (pattern, persona_key) — first match wins
    DOMAIN_MAP = [
        # SALES — deal qualification / MEDDPICC
        (r"narx|qancha|taklif|shartnoma|chegirma|deal|bitim|to.lov|payment|invoice|qiymat|budget", "sales-deal-strategist"),
        (r"qo.ng.iroq|discovery|suhbat tahlil|ehtiyoj nima|muammo nima|pain|nima kerak|nima xohlaydi", "sales-discovery-coach"),
        (r"pipeline|forecast|funnel|lid tiqilib|konversiya|velocity|crm tahlil|win rate", "sales-pipeline-analyst"),
        (r"taklif hujjat|proposal yoz|scop yoz|brief|commercial taklif|narx hujjat|taklif tayyorla", "sales-proposal-strategist"),
        (r"menejer coaching|call ko.rib|suhbat ко.rish|amaliyot|rep trening|sales training", "sales-coach"),
        (r"cold outreach|sovuq xabar|linkedin yuborish|outbound|prospecting|lead izla", "sales-outbound-strategist"),
        (r"account boshqar|klient kengayti|upsell|cross.sell|renewal|nrr|customer success", "sales-account-strategist"),
        # MARKETING
        (r"instagram|reels|stories|feed post|ig kontent", "marketing-instagram-curator"),
        (r"tiktok|viral video|hook|for you page|fyp|short video", "marketing-tiktok-strategist"),
        (r"linkedin post|thought leadership|b2b kontent|professional kontent", "marketing-linkedin-content-creator"),
        (r"seo|search|google rank|kalit so.z|organic traffic|indexing|backlink", "marketing-seo-specialist"),
        (r"smm|social media strategiya|instagram telegram bir arada|cross.platform|jamoa sahifasi", "marketing-social-media-strategist"),
        (r"o.sish|growth|akquisitsiya|viral|traffic|reklama|ads|conversion rate|kpi o'sish", "marketing-growth-hacker"),
        (r"kontent yaratish|blog|video script|podcast|infografik|editorial calendar", "marketing-content-creator"),
        # DESIGN
        (r"logo|brend|brand identity|naming|vizual|rang palitasi|brendbuk|logotip|brand guideline", "design-brand-guardian"),
        (r"ui dizayn|interfeys|figma|komponent|button|form|sayt dizayn|mobile dizayn|design system", "design-ui-designer"),
        (r"ux arxitektura|information architecture|wireframe|css tizim|layout|grid|responsive", "design-ux-architect"),
        (r"user research|foydalanuvchi|usability test|persona|journey map|ux tadqiqot", "design-ux-researcher"),
        (r"vizual hikoya|infografik|animatsiya|motion|video dizayn|brand video|visual story", "design-visual-storyteller"),
        # ENGINEERING
        (r"xavfsizlik|security|vulnerability|hack|pentest|auth|injection|owasp", "engineering-security-engineer"),
        (r"devops|docker|kubernetes|ci.cd|deploy pipeline|cloud run|terraform|infra", "engineering-devops-automator"),
        (r"code review|kod tekshir|kodni tekshir|pr tekshir|refactor tavsiya|code quality", "engineering-code-reviewer"),
        (r"backend|rest api|endpoint|graphql|microservice|database schema|server archi", "engineering-backend-architect"),
        (r"frontend|react|next\.?js|html|css|javascript|typescript|ui komponent kod", "engineering-frontend-developer"),
        (r"kod yoz|code yoz|kodni yoz|bug|xato|server error|deploy qil|hosting|python|api|database", "engineering-senior-developer"),
        # PRODUCT
        (r"user feedback|foydalanuvchi fikr|review tahlil|nps|survey natija", "product-feedback-synthesizer"),
        (r"trend|bozor tahlil|raqobatchi|market research|competitor|industry tahlil", "product-trend-researcher"),
        (r"sprint|backlog|story point|velocity|agile|scrum|task prioritet", "product-sprint-prioritizer"),
        (r"loyiha|roadmap|feature|prioritet|product strategy|mvp|release plan", "product-manager"),
        # FINANCE
        (r"investitsiya|roi|daromad|kapital|valuation|due diligence", "finance-investment-researcher"),
        (r"soliq|tax|nalog|hisobot|GAAP|audit|buxgalteriya", "finance-bookkeeper-controller"),
        (r"moliya|byudjet|budget|xarajat|foyda|p.l|cashflow|forecast moliya", "finance-fpa-analyst"),
    ]

    # Default persona per agent_id if no keyword matches
    AGENT_DEFAULTS: dict = {
        "sales": "sales-deal-strategist",
        "strategist": "product-manager",
        "researcher": "product-trend-researcher",
        "support": "sales-coach",
        "pm": "product-sprint-prioritizer",
    }

    @classmethod
    def route(
        cls,
        message: str,
        intent: str = "",
        agent_id: str = "sales",
    ) -> str:
        """
        Return a persona context block for injection into LLM prompts.
        Returns empty string if persona not found (graceful degradation).
        """
        lowered = (message + " " + intent).lower()

        for pattern, persona_key in cls.DOMAIN_MAP:
            if re.search(pattern, lowered):
                persona = AGENCY_PERSONAS.get(persona_key, "")
                if persona:
                    return f"\n\n[AGENCY PERSONA: {persona_key}]\n{persona}"

        # Fall back to agent-type default
        default_key = cls.AGENT_DEFAULTS.get(agent_id, "sales-deal-strategist")
        persona = AGENCY_PERSONAS.get(default_key, "")
        return f"\n\n[AGENCY PERSONA: {default_key}]\n{persona}" if persona else ""

    @classmethod
    def route_key(
        cls,
        message: str,
        intent: str = "",
        agent_id: str = "sales",
    ) -> Optional[str]:
        """Return just the matched persona key (no content), or None."""
        lowered = (message + " " + intent).lower()
        for pattern, persona_key in cls.DOMAIN_MAP:
            if re.search(pattern, lowered):
                if persona_key in AGENCY_PERSONAS:
                    return persona_key
        return cls.AGENT_DEFAULTS.get(agent_id)
