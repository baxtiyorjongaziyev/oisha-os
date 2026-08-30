"""
Dataclasses and constants for Oisha Product Suite.
"""
from __future__ import annotations

from dataclasses import dataclass

DEEPSALES_URL = "https://deepsales.uz/?lang=en"
METASELL_URL = "https://metasell.ai/"
REPORTAGRAM_URL = "https://www.reportagram.com/"


@dataclass(frozen=True)
class ProductPillar:
    source_product: str
    source_url: str
    oisha_layer: str
    job_to_be_done: str
    capabilities: list[str]
    oisha_modules: list[str]
    crm_outputs: list[str]


@dataclass(frozen=True)
class UnifiedWorkflow:
    key: str
    name: str
    trigger: str
    inputs: list[str]
    actions: list[str]
    outputs: list[str]


@dataclass(frozen=True)
class CallTagPolicy:
    tag: str
    description: str
    crm_action: str
    create_sales_task: bool


@dataclass(frozen=True)
class TaskDecisionRule:
    key: str
    when: str
    task_title: str
    due_in: str
    owner: str


@dataclass(frozen=True)
class RnpSignal:
    key: str
    name: str
    source: str
    oisha_action: str
    evidence_required: list[str]
