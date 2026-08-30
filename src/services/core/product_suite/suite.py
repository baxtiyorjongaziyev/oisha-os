"""
Product Suite builder.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.services.core.product_suite.definitions import (
    get_call_tag_policy,
    get_product_pillars,
    get_rnp_signals,
    get_task_decision_rules,
    get_unified_workflows,
)


def build_oisha_sales_os_suite() -> dict[str, Any]:
    pillars = get_product_pillars()
    workflows = get_unified_workflows()
    tag_policy = get_call_tag_policy()
    task_rules = get_task_decision_rules()
    rnp_signals = get_rnp_signals()

    return {
        "name": "Oisha Sales OS",
        "rnp_mission": {
            "name": "RNP - Ruka Na Pulse",
            "description": (
                "Oisha-OS rahbarning qo'lini biznes pulsida ushlab turadi: "
                "vaziyatni doim nazorat qiladi, muhim o'zgarishlarni vaqtida "
                "sezadi va fake raqamsiz, dalilga tayangan signal beradi."
            ),
            "principles": [
                "Doimiy nazorat",
                "Muhim jarayonlardan xabardorlik",
                "Vaqtida signal",
                "Evidence-first reporting",
                "Fake metrics are forbidden",
            ],
        },
        "positioning": (
            "Oisha combines DeepSales-style lead intelligence, Metasell-style "
            "conversation intelligence, and Reportagram-style revenue reporting "
            "inside one amoCRM and Telegram automation layer."
        ),
        "source_products": [
            {"name": pillar.source_product, "url": pillar.source_url}
            for pillar in pillars
        ],
        "pillars": [asdict(pillar) for pillar in pillars],
        "unified_workflows": [asdict(workflow) for workflow in workflows],
        "rnp_signals": [asdict(signal) for signal in rnp_signals],
        "call_tag_policy": [asdict(policy) for policy in tag_policy],
        "task_decision_rules": [asdict(rule) for rule in task_rules],
        "amo_crm_outputs": [
            "Structured lead profile note",
            "Uzbek transcript and conversation summary",
            "Tags: mijoz, jamoa, shaxsiy, oila, noma'lum, objection, hot_lead",
            "Next-step task with owner and due date",
            "Daily, weekly, and monthly revenue reports",
        ],
        "runtime_integrations": [
            "amoCRM",
            "Telegram bot",
            "Telegram userbot",
            "Call recordings",
            "Turso/libSQL",
            "Airtable",
        ],
    }
