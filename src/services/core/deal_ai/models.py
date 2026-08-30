"""
Models and prompt templates for Deal AI Analyzer.
"""
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
USERNAME_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{5,32})")

CATEGORY_TAGS = {
    "REAL_CLIENT": "OISHA_AI_REAL_CLIENT",
    "JUNK": "OISHA_AI_JUNK",
    "PERSONAL": "OISHA_AI_PERSONAL",
    "SPAM": "OISHA_AI_SPAM",
    "TEST": "OISHA_AI_TEST_DEAL",
    "UNCLEAR": "OISHA_AI_UNCLEAR",
}

CATEGORY_LABEL_UZ = {
    "REAL_CLIENT": "Haqiqiy mijoz",
    "JUNK": "Bekorchi / keraksiz",
    "PERSONAL": "Shaxsiy aloqa",
    "SPAM": "Spam / noto'g'ri raqam",
    "TEST": "Test yoki ichki sdelka",
    "UNCLEAR": "Aniq emas, ko'rib chiqing",
}

ANALYZER_PROMPT = """Sen Jon Branding agentligi uchun ishlovchi AmoCRM auditor agentisan.
Sening vazifang — bitta sdelkani (lead) tahlil qilib, uning ahamiyatini
quyidagi 6 ta kategoriyadan biriga ajratish:

REAL_CLIENT — haqiqiy mijoz, sotuv potensiali bor
JUNK        — bekorchi sdelka, hech qanday tijoriy qiymat yo'q
PERSONAL    — shaxsiy aloqa (oila, do'st, qarindosh)
SPAM        — spam, noto'g'ri raqam yoki bot
TEST        — ichki test sdelka yoki dublikat
UNCLEAR     — yetarli ma'lumot yo'q

Sen quyidagilarni hisobga olasan:
- Sdelka nomi va statusi
- AmoCRM dagi izohlar va custom fieldlar
- Telegram suhbatdan oxirgi xabarlar (agar mavjud)

JSON formatida javob ber, qo'shimcha matn yozma:

{
  "category": "REAL_CLIENT|JUNK|PERSONAL|SPAM|TEST|UNCLEAR",
  "confidence": 0.0,            // 0-1 oraliqda
  "reason": "qisqacha sabab (1 jumla, o'zbek tilida)",
  "evidence": ["dalil 1", "dalil 2"],  // ko'pi bilan 4 ta
  "recommended_action": "qisqa tavsiya (1 jumla)"
}
"""


@dataclass
class DealAnalysis:
    lead_id: int
    lead_name: str
    pipeline_id: Optional[int] = None
    status_id: Optional[int] = None
    category: str = "UNCLEAR"
    confidence: float = 0.0
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = ""
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None
    telegram_phone: Optional[str] = None
    messages_sampled: int = 0
    tag_applied: Optional[str] = None
    note_applied: bool = False
    status: str = "analyzed"


@dataclass
class AnalyzerReport:
    generated_at: str
    checked: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    dry_run: bool = True
    items: List[DealAnalysis] = field(default_factory=list)


def report_to_dict(report: AnalyzerReport) -> Dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "checked": report.checked,
        "by_category": report.by_category,
        "dry_run": report.dry_run,
        "items": [asdict(item) for item in report.items],
    }
