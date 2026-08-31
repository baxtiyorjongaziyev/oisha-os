"""
Contract Markdown/HTML Templates for Jon Branding services.
"""
from __future__ import annotations

from typing import Dict
from src.agents.contracts.models import ContractTemplate


def load_contract_templates() -> Dict[str, ContractTemplate]:
        """Shartnoma shablonlarini yuklash"""

        branding_template = """
# SHARTNOMA

## Tomonlar:
Bajaruvchi: "Jon.Branding" MCHJ (keyingi o'rinlarda "Agentlik")
Buyurtmachi: {{CLIENT_NAME}} (keyingi o'rinlarda "Mijoz")

## 1. Shartnoma predmeti
Agentlik Mijozga quyidagi xizmatlarni taqdim etadi:
{{SERVICE_SCOPE}}

## 2. Muddati
Boshlanish: {{START_DATE}}
Tugash: {{END_DATE}}
Umumiy muddat: {{TIMELINE}}

## 3. Narx va to'lov tartibi
Umumiy shartnoma qiymati: {{TOTAL_PRICE}} so'm
To'lov jadvali:
- 50% boshlanishda: {{DOWN_PAYMENT}} so'm
- 50% qabul qilishda: {{FINAL_PAYMENT}} so'm

## 4. Kafolatlar
- 30 kunlik bepul tuzatish muddati
- Sifat kafolati
{{GUARANTEES}}

## 5. Tomonlarning majburiyatlari
### Agentlik:
- Loyihani muddati ichida bajarish
- Mijoz bilan muntazam aloqada bo'lish
- Sifat standartlariga rioya qilish

### Mijoz:
- Tezda feedback berish
- Kerakli materiallarni taqdim etish
- To'lovlarni o'z vaqtida amalga oshirish

## 6. Force Majeure
Kuch majburiy vaziyatlar yuz berganda tomonlar bir-biridan xabar qilish majburiyatini oladi.

## 7. Nizolar hal qilish
Nizolar kelishuv orqali hal qilinadi, kelishuv bo'lmasa - O'zbekiston Respublikasi qonunchiligiga asosan.

## 8. Aloqa
Agentlik: +998 90 123 45 67, info@jonbranding.uz
Mijoz: {{CLIENT_PHONE}}, {{CLIENT_EMAIL}}

---
Imzolar:

Agentlik: _________________   Sana: {{SIGN_DATE}}
Mijoz: _________________     Sana: {{SIGN_DATE}}
"""

        web_template = """
# VEB-LOYIHA SHARTNOMASI

## Tomonlar:
Bajaruvchi: "Jon.Branding" MCHJ
Buyurtmachi: {{CLIENT_NAME}}

## 1. Xizmat doirasi
{{SERVICE_SCOPE}}

## 2. Texnik talablar
- Responsive dizayn
- SEO optimallashtirish
- Asosiy xavfsizlik

## 3. Muddati va bosqichlar
{{TIMELINE}}

## 4. Narx
Umumiy: {{TOTAL_PRICE}} so'm
{{PAYMENT_TERMS}}

## 5. Intellektual mulk
Sayt dizayni va kodi Agentlik mulki bo'lib qoladi, kontent Mijozga tegishli.

## 6. Texnik qo'llab-quvvatlash
30 kunlik bepul support, keyin har oy {{SUPPORT_PRICE}} so'm.

---
Imzolar:
Agentlik: _______   Mijoz: _______   Sana: {{SIGN_DATE}}
"""

        return {
            "branding": ContractTemplate(
                name="Brand Identity Contract",
                service_type="branding",
                base_template=branding_template,
                clauses=[
                    {
                        "title": "Revision Policy",
                        "text": "3 ta bepul revision, keyingilar 500,000 so'm",
                    },
                    {
                        "title": "Source Files",
                        "text": "Source fayllar shartnoma tugagach beriladi",
                    },
                ],
                variables=[
                    "CLIENT_NAME",
                    "SERVICE_SCOPE",
                    "TOTAL_PRICE",
                    "TIMELINE",
                    "START_DATE",
                    "END_DATE",
                ],
            ),
            "web": ContractTemplate(
                name="Web Development Contract",
                service_type="web",
                base_template=web_template,
                clauses=[
                    {
                        "title": "Hosting",
                        "text": "Hosting Mijoz tomonidan ta'minlanadi",
                    },
                    {"title": "Domain", "text": "Domain Mijoz mulki"},
                ],
                variables=[
                    "CLIENT_NAME",
                    "SERVICE_SCOPE",
                    "TOTAL_PRICE",
                    "TIMELINE",
                    "SUPPORT_PRICE",
                ],
            ),
            "marketing": ContractTemplate(
                name="Marketing Services Contract",
                service_type="marketing",
                base_template=branding_template,  # Similar structure
                clauses=[
                    {"title": "Performance", "text": "KPI lar har oy baholanadi"},
                    {
                        "title": "Ad Spend",
                        "text": "Reklama byudjeti Mijoz tomonidan qoplanadi",
                    },
                ],
                variables=[
                    "CLIENT_NAME",
                    "SERVICE_SCOPE",
                    "TOTAL_PRICE",
                    "TIMELINE",
                    "KPI_TARGETS",
                ],
            ),
        }
