"""Evidence-limited staff check-in rendering; no inferred call content."""
from typing import Mapping


def render(activity: Mapping | None) -> str | None:
    if activity is None:
        return None
    values = [activity.get(key) for key in ('total', 'answered', 'solid')]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        return None
    total, answered, solid = values
    if not solid <= answered <= total:
        return None
    return (
        f"Oxirgi soatda Moizvonki ma'lumoti: {total} ta urinish, "
        f"{answered} ta javobli va {solid} ta kamida 3 daqiqalik suhbat. "
        "Bu raqamlar suhbat sifati yoki sotuvni tasdiqlamaydi. "
        "Keyingi qadamni aniqlash uchun qaysi mijoz bo'yicha yordam kerakligini "
        "shu xabarga javoban yozishingiz mumkin."
    )
