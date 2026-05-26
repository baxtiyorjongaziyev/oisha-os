"""
Contract Generator - Avtomatik shartnoma yaratish
Oisha-OS Legal Automation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from datetime import datetime, timedelta


@dataclass
class ContractTemplate:
    """Shartnoma shabloni"""

    name: str
    service_type: str
    base_template: str
    clauses: List[Dict[str, str]]
    variables: List[str]


class ContractGenerator:
    """
    Avtomatik shartnoma yaratuvchi
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, ContractTemplate]:
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

    def generate_contract(
        self, service_type: str, client_data: Dict[str, Any], deal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Shartnoma yaratish"""

        template = self.templates.get(service_type, self.templates["branding"])

        # Calculate dates
        start_date = datetime.now()
        timeline_days = deal_data.get("timeline_days", 14)
        end_date = start_date + timedelta(days=timeline_days)

        # Prepare variables
        variables = {
            "CLIENT_NAME": client_data.get("name", "Mijoz"),
            "CLIENT_PHONE": client_data.get("phone", "___"),
            "CLIENT_EMAIL": client_data.get("email", "___"),
            "SERVICE_SCOPE": self._format_scope(deal_data.get("scope", [])),
            "TOTAL_PRICE": f"{deal_data.get('value', 0):,.0f}",
            "DOWN_PAYMENT": f"{deal_data.get('value', 0) * 0.5:,.0f}",
            "FINAL_PAYMENT": f"{deal_data.get('value', 0) * 0.5:,.0f}",
            "TIMELINE": f"{timeline_days} ish kuni",
            "START_DATE": start_date.strftime("%d.%m.%Y"),
            "END_DATE": end_date.strftime("%d.%m.%Y"),
            "SIGN_DATE": start_date.strftime("%d.%m.%Y"),
            "GUARANTEES": self._format_guarantees(deal_data.get("guarantees", [])),
            "SUPPORT_PRICE": "500,000",
            "KPI_TARGETS": deal_data.get("kpi", "KPI lar alohida kelishiladi"),
            "PAYMENT_TERMS": self._format_payment_terms(deal_data.get("value", 0)),
        }

        # Replace variables in template
        contract_text = template.base_template
        for var, value in variables.items():
            contract_text = contract_text.replace(f"{{{{{var}}}}}", str(value))

        # Add specific clauses
        contract_text += "\n\n## Qo'shimcha bandlar\n"
        for clause in template.clauses:
            contract_text += f"\n### {clause['title']}\n{clause['text']}\n"

        contract_id = f"CNT-{datetime.now().strftime('%Y%m%d')}-{client_data.get('user_id', 'XXX')[:4]}"

        # Proposal Strategist 3-Act executive summary (placed first)
        executive_summary = self._build_executive_summary(service_type, client_data, deal_data)
        full_text = executive_summary + "\n\n---\n\n" + contract_text

        return {
            "contract_id": contract_id,
            "service_type": service_type,
            "text": full_text,
            "variables": variables,
            "clauses": template.clauses,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
            "requires_approval": deal_data.get("value", 0)
            > 10000,  # 10k dan yuqori bo'lsa tasdiqlash kerak
        }

    def _build_executive_summary(
        self, service_type: str, client_data: Dict[str, Any], deal_data: Dict[str, Any]
    ) -> str:
        """Proposal Strategist 3-Act narrative — executive summary placed first.

        Act I: Mirror buyer's situation | Act II: Solution journey | Act III: Transformed state
        """
        client_name = client_data.get("name", "Mijoz")
        value = deal_data.get("value", 0)
        scope_items = deal_data.get("scope", [])
        guarantees = deal_data.get("guarantees", ["30 kunlik bepul tuzatish", "Sifat kafolati"])
        timeline_days = deal_data.get("timeline_days", 14)

        scope_text = ", ".join(scope_items) if scope_items else f"{service_type} xizmatlari"
        guarantees_text = " | ".join(guarantees)

        service_labels = {
            "branding": "brend identifikatsiya",
            "web": "veb-sayt ishlab chiqish",
            "marketing": "marketing xizmatlari",
        }
        service_label = service_labels.get(service_type, service_type)

        summary = f"""# TIJORAT TAKLIFI — EXECUTIVE SUMMARY
**Mijoz:** {client_name}  **Xizmat:** {service_label.title()}  **Qiymat:** {value:,.0f} so'm

## Act I — Vaziyatni tushunish
{client_name} {service_label} sohasida aniq biznes maqsadlariga ega. Ushbu taklif shu ehtiyojni to'liq qamrab oladi: {scope_text}.

## Act II — Yechim yo'li
Jon.Branding {timeline_days} ish kunida quyidagi bosqichlar bo'yicha natija yetkazib beradi:
- **Bosqich 1:** Konsultatsiya va strategiya (1-3 kun)
- **Bosqich 2:** Ijro va ishlab chiqish (4-{timeline_days - 2} kun)
- **Bosqich 3:** Qabul qilish va topshirish (oxirgi 2 kun)
Har bir bosqich mijoz bilan muvofiqlashtiriladi. Surprizlar yo'q.

## Act III — O'zgartirilgan holat
Loyiha yakunida {client_name} quyidagilarga ega bo'ladi: professional {service_label}, {guarantees_text}.
Investitsiya: {value:,.0f} so'm. To'lov: 50% boshlashda, 50% qabul qilishda.
"""
        return summary.strip()

    def _format_scope(self, scope_items: List[str]) -> str:
        """Xizmat doirasini formatlash"""
        if not scope_items:
            return "Professional xizmatlar"
        return "\n".join(f"- {item}" for item in scope_items)

    def _format_guarantees(self, guarantees: List[str]) -> str:
        """Kafolatlarni formatlash"""
        if not guarantees:
            return "- Sifat kafolati"
        return "\n".join(f"- {g}" for g in guarantees)

    def _format_payment_terms(self, value: float) -> str:
        """To'lov shartlarini formatlash"""
        return f"""- 50% boshlanishda: {value * 0.5:,.0f} so'm
- 25% 50% tayyor bo'lganda: {value * 0.25:,.0f} so'm  
- 25% qabul qilishda: {value * 0.25:,.0f} so'm"""

    def quick_contract(
        self, client_name: str, service: str, price: float, timeline: str
    ) -> str:
        """Tezkor shartnoma (simplified)"""

        return f"""
┌─────────────────────────────────────────┐
│     JON.BRANDING - XIZMAT SHARTNOMA     │
└─────────────────────────────────────────┘

Mijoz: {client_name}
Xizmat: {service}
Narx: {price:,.0f} so'm
Muddat: {timeline}

To'lov:
☑ 50% boshlanishda
☑ 50% tugatganda

Kafolatlar:
✓ 30 kunlik bepul tuzatish
✓ Sifat kafolati

Boshlash uchun: "TAYYOR" deb yozing

---
Jon.Branding | info@jonbranding.uz
"""


class RiskAssessor:
    """
    Bitim risklarini baholash tizimi
    """

    def __init__(self):
        self.risk_factors = {
            "price_pressure": {"weight": 0.3, "level": "medium"},
            "competitive_pressure": {"weight": 0.4, "level": "high"},
            "legal_review": {"weight": 0.2, "level": "medium"},
            "negative_sentiment": {"weight": 0.5, "level": "high"},
            "discount_request": {"weight": 0.3, "level": "medium"},
            "unrealistic_timeline": {"weight": 0.4, "level": "high"},
            "budget_mismatch": {"weight": 0.35, "level": "medium"},
            "scope_creep": {"weight": 0.25, "level": "low"},
        }

    def assess_deal_risk(
        self,
        deal_value: float,
        client_history: Dict,
        negotiation_flags: List[str],
        service_complexity: str = "medium",
    ) -> Dict[str, Any]:
        """Bitim riskini baholash"""

        total_risk_score = 0
        risk_breakdown = []
        recommendations = []

        # Flag-based risks
        for flag in negotiation_flags:
            if flag in self.risk_factors:
                factor = self.risk_factors[flag]
                total_risk_score += factor["weight"]
                risk_breakdown.append(
                    {
                        "factor": flag,
                        "weight": factor["weight"],
                        "level": factor["level"],
                    }
                )

                # Add recommendations
                if flag == "price_pressure":
                    recommendations.append(
                        "Qiymat asoslangan ROI hisobotini taqdim eting"
                    )
                elif flag == "competitive_pressure":
                    recommendations.append(
                        "Differentiation strategiyasini kuchaytiring"
                    )
                elif flag == "negative_sentiment":
                    recommendations.append(
                        "Human manager qo'llab-quvvatlashini talab qiling"
                    )

        # Value-based risks
        if deal_value > 20000:
            total_risk_score += 0.2
            risk_breakdown.append(
                {"factor": "high_value_deal", "weight": 0.2, "level": "high"}
            )
            recommendations.append("Katta bitim: Katta direktor tasdiqlashi kerak")

        if deal_value < 1000:
            total_risk_score += 0.15
            risk_breakdown.append(
                {"factor": "low_value_deal", "weight": 0.15, "level": "low"}
            )

        # Client history risks
        if client_history.get("previous_deals", 0) == 0:
            total_risk_score += 0.1
            risk_breakdown.append(
                {"factor": "new_client", "weight": 0.1, "level": "medium"}
            )
            recommendations.append("Yangi mijoz: 100% oldindan to'lov talab qiling")

        if client_history.get("payment_issues", False):
            total_risk_score += 0.4
            risk_breakdown.append(
                {"factor": "payment_history", "weight": 0.4, "level": "high"}
            )
            recommendations.append("To'lov muammolari: Faqat 100% oldindan to'lov")

        # Complexity risk
        complexity_weights = {"low": 0, "medium": 0.1, "high": 0.25, "enterprise": 0.35}
        complexity_risk = complexity_weights.get(service_complexity, 0.1)
        total_risk_score += complexity_risk

        # Normalize score (0-1)
        final_score = min(1.0, total_risk_score)

        # Determine level
        if final_score < 0.3:
            level = "low"
            autonomy_allowed = True
        elif final_score < 0.6:
            level = "medium"
            autonomy_allowed = True
        else:
            level = "high"
            autonomy_allowed = False

        return {
            "score": round(final_score, 2),
            "level": level,
            "autonomy_allowed": autonomy_allowed,
            "requires_approval": final_score > 0.5,
            "breakdown": risk_breakdown,
            "recommendations": recommendations,
            "contract_clauses_needed": final_score > 0.4,
        }

    def get_approval_requirements(self, risk_assessment: Dict) -> List[str]:
        """Tasdiqlash talablarini olish"""

        requirements = []

        if risk_assessment["score"] > 0.7:
            requirements.extend(
                [
                    "Senior manager tasdiqlashi",
                    "Yuridik ko'rib chiqishi",
                    "Moliyaviy tekshiruv",
                ]
            )
        elif risk_assessment["score"] > 0.5:
            requirements.extend(
                ["Manager tasdiqlashi", "Shartnoma shartlari ko'rib chiqilsin"]
            )

        if risk_assessment.get("contract_clauses_needed"):
            requirements.append("Qo'shimcha himoya bandlari qo'shilsin")

        return requirements
