"""
Airtable field maps, writable aliases, allowed fields, and terminal stages.
"""
import os

READ_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 20
BILLING_COOLDOWN_SECONDS = int(
    os.getenv("AIRTABLE_BILLING_COOLDOWN_SECONDS", "21600")
)

_base_tables_cache = {}
_record_url_cache = {}
_records_cache = {}
_billing_blocked_until = 0.0
_billing_block_reason = None

# Field name mapping: code key -> actual Airtable field names (priority order)
FIELD_MAP = {
    "stage": ["Loyiha bosqichi", "Stage", "Status", "Holati", "Loyiha statusi"],
    "project_name": [
        "Loyihani nomi?",
        "Project Name",
        "Name",
        "Loyiha nomi",
        "Loyiha",
        "Mijoz",
        "Mijoz nomi",
        "Client",
        "Client Name",
        "Title",
        "title",
        "name",
        "Xizmat turi",
        "Xizmat",
        "Task Name",
        "Task",
    ],
    "project_id": ["Loyiha ID", "AmoCRM_ID", "Project ID", "ID"],
    "deadline": ["END sana", "Deadline", "Muddati"],
    "start_date": ["Start sana", "Created", "Start Date"],
    "budget": ["Kelishgan narx", "Jami loyiha narxi (UZS)", "Budget"],
    "budget_usd": ["Jami loyiha narxi (USD)"],
    "manager": ["PM", "Manager"],
    "payment_status": ["To'lov statusi", "To'lovlar holati"],
    "paid_usd": ["Jami to'langan USD"],
    "remaining_usd": ["Qoldiq to'lov $"],
    "summary": ["Xulosa", "Summary", "Chat Summary"],
}

PROJECT_WRITE_ALIASES = {
    "Project Name": "Loyihani nomi?",
    "Name": "Loyihani nomi?",
    "Stage": "Loyiha bosqichi",
    "Status": "Loyiha bosqichi",
    "Budget": "Kelishgan narx",
    "Jami loyiha narxi (UZS)": "Kelishgan narx",
    "Created At": "Start sana",
    "Summary": "Xulosa",
    "Chat Summary": "Xulosa",
}

# Writable fields in the current "Loyihalar" schema.
PROJECT_ALLOWED_FIELDS = {
    "Loyihani nomi?",
    "Loyiha bosqichi",
    "Start sana",
    "END sana",
    "Kelishgan narx",
    "To'lovlar holati",
    "Turi",
    "Kurs",
    "Muhim darajasi",
    "Xizmat turi",
    "PM",
    "Manager",
    "Xulosa",
}

DONE_STAGES = [
    "Yakunlangan",
    "Done",
    "Completed",
    "Topshirildi",
    "Arxiv",
    "Fayllarni yetkazib berish va topshirish",
]
