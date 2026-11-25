"""Ishga nomzod (HR) qöngʻiroqlarini savdo suhbatlaridan ajratish."""
import re
from typing import Any

# Faqat butun söz sifatida. Savdo matnida uchraydigan umumiy iboralar
# ("taklif", "ish") ataylab kiritilmagan.
_RECRUITMENT_PATTERN = re.compile(
    r"\bhead\s*hunter\b|\bhh\.uz\b|\bvakansiya\w*|\brezyume\w*|\brezume\w*|"
    r"\bрезюме|\bвакансия|\bnomzod\w*|"
    r"\bishga\s+(?:kirish|qabul|joylash|ariza)\w*|\bсобеседовани",
    re.IGNORECASE,
)


def apply_recruitment_override(category: str, summary: Any) -> str:
    """AI "Mijoz" desa ham, xulosada ishga qabul belgilari bölsa "Jamoa"."""
    if category != "Mijoz":
        return category
    if _RECRUITMENT_PATTERN.search(str(summary or "")):
        return "Jamoa"
    return category
