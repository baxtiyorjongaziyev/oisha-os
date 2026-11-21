"""Resolve a shared-login CRM task to one explicitly identified seller."""
from dataclasses import dataclass

SELLER_FIELD_ID = 1559389


@dataclass(frozen=True)
class Seller:
    name: str
    username: str
    chat_id: int


# Owner-confirmed roster; IDs verified using the running Telegram client 2026-11-21.
SELLERS = {
    "rayxon": Seller("Rayxon", "RayxonJonbranding", 8878762085),
    "shahnoza": Seller("Shahnoza", "jonbranding_assistant", 8802892610),
    "mumtozmaxal": Seller("Mumtozmaxal", "MumtozmaxalJonbranding", 8940413540),
}
ALIASES = {"rayxona": "rayxon", "mumtozmahal": "mumtozmaxal"}


def _seller_key(value):
    key = str(value or "").strip().casefold()
    key = ALIASES.get(key, key)
    return key if key in SELLERS else None


def resolve_seller(lead):
    """Unknown values or conflicting field/tags block private disclosure."""
    if not isinstance(lead, dict):
        return None
    field_keys = set()
    for field in lead.get("custom_fields_values") or []:
        if str(field.get("field_id")) != str(SELLER_FIELD_ID):
            continue
        for entry in field.get("values") or []:
            value = entry.get("value")
            if value:
                key = _seller_key(value)
                if not key:
                    return None
                field_keys.add(key)
    tag_keys = {
        key for tag in (lead.get("_embedded") or {}).get("tags", [])
        if (key := _seller_key(tag.get("name")))
    }
    keys = field_keys | tag_keys
    if len(keys) != 1:
        return None
    return SELLERS[next(iter(keys))]
