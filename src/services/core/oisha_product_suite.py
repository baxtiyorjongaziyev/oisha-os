from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


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


def get_product_pillars() -> list[ProductPillar]:
    return [
        ProductPillar(
            source_product="DeepSales",
            source_url=DEEPSALES_URL,
            oisha_layer="Lead Intelligence",
            job_to_be_done=(
                "Find the real buyer context behind a phone number or lead and "
                "prioritize the highest-intent opportunities."
            ),
            capabilities=[
                "Phone-based lead enrichment",
                "Buyer persona and source detection",
                "Lead quality scoring",
                "Duplicate and noisy lead cleanup",
                "Next best action recommendation",
            ],
            oisha_modules=[
                "AmoCRMLeadEnricher",
                "LeadScraper",
                "LeadClassifier",
                "DealHygiene",
                "TelegramTaskCreator",
            ],
            crm_outputs=[
                "Lead score",
                "Enrichment note",
                "Lead source tag",
                "Qualification task",
            ],
        ),
        ProductPillar(
            source_product="Metasell",
            source_url=METASELL_URL,
            oisha_layer="Conversation Intelligence",
            job_to_be_done=(
                "Listen to every customer conversation, transcribe it, coach the "
                "manager, and decide the next CRM action."
            ),
            capabilities=[
                "Call recording transcription",
                "Uzbek summary and objection extraction",
                "Sales script compliance scoring",
                "Manager coaching recommendations",
                "Automatic task and tag creation from conversation outcome",
            ],
            oisha_modules=[
                "CallAnalyzer",
                "PipelineAuditor",
                "SalesCoach",
                "AutonomousSalesAgent",
                "Telegram userbot context bridge",
            ],
            crm_outputs=[
                "Call transcript note",
                "Conversation summary",
                "Objection tags",
                "Follow-up task",
                "Manager coaching note",
            ],
        ),
        ProductPillar(
            source_product="Reportagram",
            source_url=REPORTAGRAM_URL,
            oisha_layer="Revenue Reporting",
            job_to_be_done=(
                "Turn sales and marketing activity into scheduled reports that "
                "show funnel health, speed, revenue, and bottlenecks."
            ),
            capabilities=[
                "Daily, weekly, and monthly reports",
                "Funnel conversion and revenue metrics",
                "Manager leaderboard",
                "Slow response and stale deal alerts",
                "Telegram-ready executive summary",
            ],
            oisha_modules=[
                "EnterpriseReporter",
                "SalesAnalytics",
                "MissionControl",
                "SlaMonitor",
                "WorkflowManager",
            ],
            crm_outputs=[
                "Daily report",
                "Weekly report",
                "Monthly report",
                "SLA alert task",
                "Pipeline audit note",
            ],
        ),
    ]


def get_unified_workflows() -> list[UnifiedWorkflow]:
    return [
        UnifiedWorkflow(
            key="lead_arrival",
            name="Lead arrival intelligence",
            trigger="New amoCRM deal or incoming phone number",
            inputs=[
                "amoCRM lead/contact fields",
                "Phone number",
                "Telegram userbot chat history when available",
                "Lead source and UTM data",
            ],
            actions=[
                "Normalize and deduplicate phone number",
                "Enrich buyer context",
                "Classify lead quality and intent",
                "Write a structured note into amoCRM",
            ],
            outputs=[
                "Enriched lead profile",
                "Lead quality tag",
                "First next-step task",
            ],
        ),
        UnifiedWorkflow(
            key="call_completed",
            name="Call and chat analysis",
            trigger="New call recording or completed Telegram conversation",
            inputs=[
                "Call recording",
                "Telegram messages",
                "Lead stage",
                "Manager identity",
            ],
            actions=[
                "Transcribe audio",
                "Summarize in Uzbek",
                "Extract objections, promises, and next steps",
                "Classify conversation type",
                "Create amoCRM note and task",
            ],
            outputs=[
                "Uzbek transcript",
                "Conversation summary",
                "Tags",
                "Task for next action",
            ],
        ),
        UnifiedWorkflow(
            key="pipeline_health",
            name="Revenue reporting and audit",
            trigger="Scheduled daily, weekly, and monthly reporting window",
            inputs=[
                "amoCRM deals",
                "Call analysis results",
                "Tasks",
                "Revenue and conversion metrics",
            ],
            actions=[
                "Calculate funnel metrics",
                "Find stalled deals and response delays",
                "Rank managers",
                "Send Telegram report",
                "Open CRM tasks for risky deals",
            ],
            outputs=[
                "Executive report",
                "Pipeline risk list",
                "Manager leaderboard",
                "SLA tasks",
            ],
        ),
        UnifiedWorkflow(
            key="autonomous_follow_up",
            name="Autonomous next-best-action",
            trigger="Conversation result, missed SLA, or high-intent signal",
            inputs=[
                "Lead enrichment",
                "Call summary",
                "Objection tags",
                "Current CRM stage",
            ],
            actions=[
                "Choose follow-up strategy",
                "Assign owner",
                "Set due date",
                "Write reason into amoCRM",
            ],
            outputs=[
                "Owner-specific task",
                "CRM note with reasoning",
                "Escalation tag when needed",
            ],
        ),
    ]


def get_call_tag_policy() -> list[CallTagPolicy]:
    return [
        CallTagPolicy(
            tag="mijoz",
            description="Real customer or buyer conversation.",
            crm_action="Keep in pipeline, write summary, and create next sales task.",
            create_sales_task=True,
        ),
        CallTagPolicy(
            tag="jamoa",
            description="Internal team or manager coordination.",
            crm_action="Write internal note and avoid polluting sales conversion metrics.",
            create_sales_task=False,
        ),
        CallTagPolicy(
            tag="shaxsiy",
            description="Personal call that is not related to the customer journey.",
            crm_action="Tag as personal/noise and exclude from sales analysis.",
            create_sales_task=False,
        ),
        CallTagPolicy(
            tag="oila",
            description="Family call or private context.",
            crm_action="Tag as private/noise and exclude from sales analysis.",
            create_sales_task=False,
        ),
        CallTagPolicy(
            tag="noma'lum",
            description="Unclear or mixed conversation that needs human review.",
            crm_action="Create a review task only when the lead is still active.",
            create_sales_task=True,
        ),
    ]


def get_task_decision_rules() -> list[TaskDecisionRule]:
    return [
        TaskDecisionRule(
            key="hot_lead",
            when="Customer has high intent, asks price, timing, availability, or next step.",
            task_title="Follow up with concrete offer",
            due_in="2 hours",
            owner="Responsible manager",
        ),
        TaskDecisionRule(
            key="price_objection",
            when="Conversation contains price objection or ROI concern.",
            task_title="Send value proof and objection handling script",
            due_in="4 hours",
            owner="Responsible manager",
        ),
        TaskDecisionRule(
            key="missed_callback",
            when="Manager promised to call back or customer asked to be contacted later.",
            task_title="Call back at promised time",
            due_in="Promised time, otherwise next business day",
            owner="Responsible manager",
        ),
        TaskDecisionRule(
            key="manager_quality_gap",
            when="Manager skipped greeting, discovery, objection handling, or closing.",
            task_title="Review coaching note and improve next call",
            due_in="1 day",
            owner="Sales lead",
        ),
        TaskDecisionRule(
            key="non_sales_noise",
            when="Call is personal, family, or internal team conversation.",
            task_title="No sales follow-up required",
            due_in="None",
            owner="System",
        ),
    ]


def get_rnp_signals() -> list[RnpSignal]:
    return [
        RnpSignal(
            key="new_lead",
            name="Yangi lead tushdi",
            source="amoCRM",
            oisha_action=(
                "Leadni tekshiradi, duplicate ehtimolini ko'radi, javob/follow-up "
                "vazifasini nazorat qiladi."
            ),
            evidence_required=["amoCRM lead id", "contact phone or source"],
        ),
        RnpSignal(
            key="stale_lead",
            name="Lead qotib qoldi",
            source="amoCRM",
            oisha_action="Mas'ul menejerga aniq keyingi qadam taskini yozadi.",
            evidence_required=["amoCRM lead id", "updated_at", "responsible_user_id"],
        ),
        RnpSignal(
            key="unanswered_customer",
            name="Mijoz Telegramda javobsiz qoldi",
            source="Telegram userbot",
            oisha_action=(
                "Chat kontekstini tekshiradi, shaxsiy/oila bo'lmasa signal beradi "
                "yoki follow-up draft tayyorlaydi."
            ),
            evidence_required=["telegram chat id", "last incoming message", "private-policy classification"],
        ),
        RnpSignal(
            key="meeting_agreed",
            name="Uchrashuv kelishildi",
            source="Telegram userbot + amoCRM",
            oisha_action=(
                "Lead mavjud bo'lsa amoCRM task qo'yadi, mavjud bo'lmasa review "
                "signal beradi."
            ),
            evidence_required=["telegram message reference", "date/time", "matched lead id or review reason"],
        ),
        RnpSignal(
            key="call_recording_ready",
            name="Qo'ng'iroq yozuvi bor",
            source="amoCRM",
            oisha_action="Transkripsiya, xulosa, objection va keyingi qadam chiqaradi.",
            evidence_required=["amoCRM call id", "lead id", "audio url"],
        ),
        RnpSignal(
            key="manager_quality_drop",
            name="Menejer sifati pasaydi",
            source="amoCRM call analysis",
            oisha_action="Coaching signal beradi va ko'rib chiqiladigan callni ko'rsatadi.",
            evidence_required=["scorecard id", "weak rubric criteria", "call link"],
        ),
        RnpSignal(
            key="source_unhealthy",
            name="Manba ishlamayapti",
            source="runtime health",
            oisha_action=(
                "Raqam o'ylab topmaydi, qaysi manba ishlamayotganini aniq aytadi."
            ),
            evidence_required=["source name", "health status", "last successful sync"],
        ),
    ]


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
