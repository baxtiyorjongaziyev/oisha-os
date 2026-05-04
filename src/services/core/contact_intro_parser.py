import re
from dataclasses import dataclass
from typing import Optional


_FIELD_ALIASES = {
    "first_name": {"ism", "ismi", "name"},
    "last_name": {"familiya", "familya", "family name", "surname"},
    "birthday": {"tug'ilgan kun", "tugilgan kun", "tug'ilgan kuni", "tugilgan kuni", "birthday"},
    "birthplace": {"tug'ilgan joy", "tugilgan joy", "tug'ilgan joyi", "tugilgan joyi"},
    "brand": {"brend", "brand", "kompaniya", "company"},
    "activity": {"faoliyat turi", "faoliyati", "soha", "yo'nalish", "yonalish", "activity"},
    "region": {"faoliyat hududi", "hudud", "shahar", "region", "city"},
    "position": {"lavozim", "position", "role"},
    "phone": {"tel", "telefon", "raqam", "phone", "mobile"},
    "telegram": {"telegram", "tg"},
    "instagram": {"instagram", "insta"},
}

_PHONE_RE = re.compile(r"(?:(?:\+|00)?998[\s\-()]*)?(?:\d[\s\-()]*){9,12}")
_USERNAME_RE = re.compile(r"@[\w\d_]{4,32}")
_BULLET_RE = re.compile(r"^[\s\u2705\u2611\ufe0f\u2714\u25aa\u2022\-\*]+")
_LABEL_RE = re.compile(r"^\s*([^:\uff1a\-\u2013\u2014]+?)\s*[:\uff1a\-\u2013\u2014]\s*(.+?)\s*$")
_APOSTROPHES = ("\u2019", "\u2018", "\u02bc", "\u02bb", "`", "\u00b4")


@dataclass(frozen=True)
class ContactIntro:
    first_name: str
    last_name: str
    phone: str
    telegram: str = ""
    instagram: str = ""
    birthday: str = ""
    birthplace: str = ""
    brand: str = ""
    activity: str = ""
    region: str = ""
    position: str = ""
    source_chat: str = ""
    original_text: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_name, self.last_name] if part).strip()

    @property
    def group_label(self) -> str:
        if self.source_chat and "tez natija" in self.source_chat.lower():
            return "TEZ NATIJA"
        return "Telegram Intro"

    @property
    def note(self) -> str:
        lines = [
            "Avtomatik saqlandi: Telegram guruhidagi tanishtiruv posti",
            f"Manba guruh: {self.source_chat or 'Nomalum'}",
            f"Brend: {self.brand or 'Nomalum'}",
            f"Faoliyat: {self.activity or 'Nomalum'}",
            f"Hudud: {self.region or 'Nomalum'}",
            f"Lavozim: {self.position or 'Nomalum'}",
            f"Tug'ilgan kun: {self.birthday or 'Nomalum'}",
            f"Tug'ilgan joy: {self.birthplace or 'Nomalum'}",
            f"Telegram: {self.telegram or 'Nomalum'}",
            f"Instagram: {self.instagram or 'Nomalum'}",
            "",
            "Original post:",
            self.original_text[:1500],
        ]
        return "\n".join(lines)


def _normalize_label(label: str) -> Optional[str]:
    clean = _BULLET_RE.sub("", label).strip().lower()
    for apostrophe in _APOSTROPHES:
        clean = clean.replace(apostrophe, "'")
    clean = re.sub(r"\s+", " ", clean)
    for field_name, aliases in _FIELD_ALIASES.items():
        if clean in aliases:
            return field_name
    return None


def _normalize_value(value: str) -> str:
    return _BULLET_RE.sub("", value).strip().strip(":").strip()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if digits.startswith("998") and len(digits) > 12:
        return "+" + digits[:12]
    return "+" + digits if value.strip().startswith("+") and digits else digits


def _extract_phone(text: str) -> str:
    for match in _PHONE_RE.finditer(text or ""):
        phone = normalize_phone(match.group(0))
        if phone.startswith("+998") and len(re.sub(r"\D", "", phone)) == 12:
            return phone
    return ""


def _extract_usernames(text: str) -> list[str]:
    return _USERNAME_RE.findall(text or "")


def parse_contact_intro(text: str, source_chat: str = "") -> Optional[ContactIntro]:
    """Parse Uzbek/Russian-style Telegram intro posts into contact data.

    The parser is conservative on purpose: it only accepts a structured
    self-introduction with a valid Uzbekistan phone number and business fields.
    That keeps the userbot from saving random phone numbers from group chats.
    """
    if not text or len(text.strip()) < 30:
        return None

    fields: dict[str, str] = {}
    current_field: Optional[str] = None
    label_hits = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _LABEL_RE.match(line)
        if match:
            field_name = _normalize_label(match.group(1))
            if field_name:
                value = _normalize_value(match.group(2))
                if value:
                    if field_name in {"instagram", "telegram"} and field_name in fields:
                        fields[field_name] = f"{fields[field_name]} {value}".strip()
                    else:
                        fields[field_name] = value
                    current_field = field_name
                    label_hits += 1
                continue

        usernames = _extract_usernames(line)
        if usernames and current_field in {"instagram", "telegram"}:
            existing = fields.get(current_field, "")
            fields[current_field] = f"{existing} {' '.join(usernames)}".strip()

    phone = normalize_phone(fields.get("phone", "")) or _extract_phone(text)
    if not (phone.startswith("+998") and len(re.sub(r"\D", "", phone)) == 12):
        return None

    first_name = fields.get("first_name", "").strip()
    last_name = fields.get("last_name", "").strip()
    telegram = fields.get("telegram", "").strip()
    if not first_name and not telegram:
        return None

    business_signal_count = sum(
        1 for key in ("brand", "activity", "region", "position") if fields.get(key)
    )
    if label_hits < 4 or business_signal_count < 2:
        return None

    return ContactIntro(
        first_name=first_name or telegram.lstrip("@"),
        last_name=last_name,
        phone=phone,
        telegram=telegram,
        instagram=fields.get("instagram", "").strip(),
        birthday=fields.get("birthday", "").strip(),
        birthplace=fields.get("birthplace", "").strip(),
        brand=fields.get("brand", "").strip(),
        activity=fields.get("activity", "").strip(),
        region=fields.get("region", "").strip(),
        position=fields.get("position", "").strip(),
        source_chat=source_chat,
        original_text=text.strip(),
    )
