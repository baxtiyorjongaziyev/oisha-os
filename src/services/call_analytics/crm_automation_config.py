"""CRM avtomatika mapping'lari (AmoCRM ID'lari).

Manbalar (repo ichida tasdiqlangan):
- Etaplar: scripts/align_sales_pipeline_to_5_stages.py (Sotuv Bo'limi, 5 etap);
  nomlar AmoCRM UI skrinshotida tasdiqlangan (2026-10-06)
- Maydonlar: src/services/core/instagram/leadgen_custom_fields.py
- Natija kalitlari: src/services/core/sales_playbook.py (OUTCOME_*)

Faqat [Text] maydonlar avto-to'ldiriladi. [Select] maydonlar enum_id talab qiladi —
ular uchun mapping qo'shilmaguncha avto-to'ldirish yo'q.
"""

from src.services.core.sales_playbook import (
    OUTCOME_MATERIALS,
    OUTCOME_MEETING,
    OUTCOME_PAYMENT,
    OUTCOME_PROPOSAL,
    OUTCOME_REFUSED,
)

SALES_PIPELINE_ID = 11162698
STATUS_YANGI = 87609514  # Yangi LEads
STATUS_ALOQA = 87609518  # Qayta aloqa
STATUS_KVALIFIKATSIYA = 87609522  # Kvalifikatsiya
STATUS_UCHRASHUV = 87609526  # Uchrashuv
STATUS_KELISHUV_YOPISH = 88871066  # Kelishuv / Yopish

# AmoCRM tizim etaplari (har voronkada bir xil): faqat menejer qo'yadi.
STATUS_WON = 142  # Sotuv bo'ldi
STATUS_LOST = 143  # Yopildi / Bekor qilindi

FIELD_BRAND_NAME = 1551701  # Brend / Biznes nomi [Text]

FIELD_MAP = {
    "mijoz_kompaniya": FIELD_BRAND_NAME,
}

STAGE_RULES = {
    "pipeline_order": [
        STATUS_YANGI,
        STATUS_ALOQA,
        STATUS_KVALIFIKATSIYA,
        STATUS_UCHRASHUV,
        STATUS_KELISHUV_YOPISH,
    ],
    "outcome_to_status": {
        OUTCOME_MATERIALS: STATUS_KVALIFIKATSIYA,
        OUTCOME_MEETING: STATUS_UCHRASHUV,
        OUTCOME_PROPOSAL: STATUS_KELISHUV_YOPISH,
        # To'lov kelishildi != Won: Won'ni menejer belgilaydi, AI faqat yopish etapiga suradi.
        OUTCOME_PAYMENT: STATUS_KELISHUV_YOPISH,
    },
    "terminal_outcomes": [OUTCOME_REFUSED],
    "closed_statuses": [STATUS_WON, STATUS_LOST],
    "min_confidence": 0.8,
}
