"""Juma tabriklari uchun anti-spam limitlari, vaqt oynasi va PCG filtri."""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
DEFAULT_BLOCKED_USERNAME_TOKENS: tuple[str, ...] = ("pcg",)
DEFAULT_BLOCKED_BRAND_TOKENS: tuple[str, ...] = (
    "amaan", "asxab", "noormarketing", "metasell", "bifoza", "patentlab",
)
DEFAULT_BLOCKED_EXACT_USERNAMES: tuple[str, ...] = (
    "nurmuhammadabdulaziz", "rahimov_erpflow", "rahimoverpflow", "sarvarbeksaibov",
)
DEFAULT_BLOCKED_USER_IDS: tuple[int, ...] = (5190113669, 8691281355)
_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ў": "o",
    "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "ъ": "", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}
JUMA_TEMPLATES: tuple[str, ...] = (
    (
        "Assalomu alaykum! Juma muborak boʻlsin 🤲\n\n"
        "Alloh xonadoningizga baraka, ishlaringizga rivoj bersin. "
        "Bugungi qilgan duolaringiz qabul boʻlib, koʻnglingiz doim xotirjam boʻlsin."
    ),
    (
        "Assalomu alaykum! Juma muborak boʻlsin! 🤲\n\n"
        "Alloh kuningizni xayrli, ishlaringizni barakali qilsin. "
        "Yaxshi niyatlaringizga yetkazsin."
    ),
    (
        "Assalomu alaykum! Juma muborak boʻlsin! 🤲\n\n"
        "Alloh rizqingizga baraka bersin, koʻnglingizni xotirjam qilsin. "
        "Niyat qilgan yaxshi ishlaringizga yetkazib, duolaringizni qabul qilsin."
    ),
)
GROUP_PRIORITY: list[dict] = [
    {"label": "Tez Natija 7", "code": "TN7", "names": ["Tez natija 7", '"TEZ NATIJA 7" UMUMIY', "TN7 Gr"], "id": int(os.environ.get("TN7_GROUP_ID", "-1003926176795"))},
    {"label": "Tez Natija 6", "code": "TN6", "names": ["Tez natija 6", '"TEZ NATIJA 6" UMUMIY', "TN6 Gr"], "id": int(os.environ.get("TN6_GROUP_ID", "-1003496493814"))},
    {"label": "Tez Natija 5", "code": "TN5", "names": ["Tez natija 5", '"TEZ NATIJA 5" UMUMIY', "TN5 Gr"], "id": int(os.environ.get("TN5_GROUP_ID", "-1003820339529"))},
    {"label": "Tez Natija 4", "code": "TN4", "names": ["Tez natija 4", '"TEZ NATIJA 4" UMUMIY', "TN4 Gr"], "id": int(os.environ.get("TN4_GROUP_ID", "-1003149348132"))},
    {"label": "Tez Natija 3", "code": "TN3", "names": ["Tez natija 3", '"TEZ NATIJA 3" UMUMIY', "TN3 Gr"], "id": int(os.environ.get("TN3_GROUP_ID", "-1002849105320"))},
    {"label": "Tez Natija 2", "code": "TN2", "names": ["Tez natija 2", '"TEZ NATIJA 2" UMUMIY', "TN2 Gr"], "id": int(os.environ.get("TN2_GROUP_ID", "-1002440481294"))},
]


@dataclass(frozen=True)
class JumaRateConfig:
    """Telegram Juma tabrigi uchun tezlik, limit va sokin soatlar sozlamalari."""

    delay_min_sec: float = 90.0
    delay_max_sec: float = 180.0
    batch_size: int = 15
    batch_pause_min_sec: float = 900.0
    batch_pause_max_sec: float = 1200.0
    cold_daily_limit: Optional[int] = None
    quiet_start: tuple[int, int] = (22, 30)
    quiet_end: tuple[int, int] = (6, 0)
    silent_until: tuple[int, int] = (8, 0)
    shom_hour: int = 17
    shom_minute: int = 0
    max_flood_wait_sec: int = 300
    typing_min_sec: float = 2.0
    typing_max_sec: float = 5.0
    blocked_username_tokens: tuple[str, ...] = DEFAULT_BLOCKED_USERNAME_TOKENS
    blocked_brand_tokens: tuple[str, ...] = DEFAULT_BLOCKED_BRAND_TOKENS
    blocked_exact_usernames: tuple[str, ...] = DEFAULT_BLOCKED_EXACT_USERNAMES
    blocked_user_ids: tuple[int, ...] = DEFAULT_BLOCKED_USER_IDS


def _compact_latin(text: Optional[str]) -> str:
    mapped = "".join(_CYR_TO_LAT.get(ch, ch) for ch in (text or "").lower())
    return "".join(ch for ch in mapped if ("a" <= ch <= "z") or ("0" <= ch <= "9"))

def _parse_int_id(value: object) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value).strip() if value is not None else ""
    return int(text) if text and text.lstrip("-").isdigit() else None

def _parse_hhmm(raw: Optional[str], default: tuple[int, int]) -> tuple[int, int]:
    text = (raw or "").strip()
    if ":" not in text:
        return default
    hour_s, _, min_s = text.partition(":")
    try:
        hour, minute = int(hour_s), int(min_s)
    except ValueError:
        return default
    return (hour, minute) if 0 <= hour <= 23 and 0 <= minute <= 59 else default

def _parse_optional_int(raw: Optional[str], default: Optional[int]) -> Optional[int]:
    if raw is None:
        return default
    text = raw.strip().lower()
    return None if text in {"", "none", "unlimited"} else max(0, int(text))

def _split_csv(raw: Optional[str], *, strip_at: bool = True) -> list[str]:
    return [c for p in (raw or "").split(",") if (c := (p.strip().lstrip("@") if strip_at else p.strip()))]

def parse_blocked_username_tokens(raw: Optional[str]) -> tuple[str, ...]:
    """Vergul bilan ajratilgan taqiqlangan username tokenlarini normallashtiradi."""
    return DEFAULT_BLOCKED_USERNAME_TOKENS if raw is None else tuple(p.lower() for p in _split_csv(raw))

def load_juma_rate_config(env: Optional[Mapping[str, str]] = None) -> JumaRateConfig:
    """Environmentdan Juma anti-spam konfiguratsiyasini oʻqiydi."""
    src = os.environ if env is None else env
    delay_min = float(src.get("JUMA_DELAY_MIN_SEC") or 90.0)
    batch_min = float(src.get("JUMA_BATCH_PAUSE_MIN_SEC") or 900.0)
    typing_min = float(src.get("JUMA_TYPING_MIN_SEC") or 2.0)
    raw_brands, raw_users, raw_ids = src.get("JUMA_EXCLUDED_BRAND_TOKENS"), src.get("JUMA_EXCLUDED_USERNAMES"), src.get("JUMA_EXCLUDED_USER_IDS")
    return JumaRateConfig(
        delay_min_sec=delay_min,
        delay_max_sec=max(delay_min, float(src.get("JUMA_DELAY_MAX_SEC") or 180.0)),
        batch_size=max(0, int(src.get("JUMA_BATCH_SIZE") or 15)),
        batch_pause_min_sec=batch_min,
        batch_pause_max_sec=max(batch_min, float(src.get("JUMA_BATCH_PAUSE_MAX_SEC") or 1200.0)),
        cold_daily_limit=_parse_optional_int(src.get("JUMA_COLD_DAILY_LIMIT"), None),
        quiet_start=_parse_hhmm(src.get("JUMA_QUIET_START"), (22, 30)),
        quiet_end=_parse_hhmm(src.get("JUMA_QUIET_END"), (6, 0)),
        silent_until=_parse_hhmm(src.get("JUMA_SILENT_UNTIL"), (8, 0)),
        shom_hour=int(src.get("JUMA_SHOM_HOUR") or 17),
        shom_minute=int(src.get("JUMA_SHOM_MINUTE") or 0),
        max_flood_wait_sec=max(0, int(src.get("JUMA_MAX_FLOOD_WAIT_SEC") or 300)),
        typing_min_sec=typing_min,
        typing_max_sec=max(typing_min, float(src.get("JUMA_TYPING_MAX_SEC") or 5.0)),
        blocked_username_tokens=parse_blocked_username_tokens(src.get("JUMA_EXCLUDED_USERNAME_TOKENS")),
        blocked_brand_tokens=DEFAULT_BLOCKED_BRAND_TOKENS if raw_brands is None else tuple(_compact_latin(p) for p in _split_csv(raw_brands) if _compact_latin(p)),
        blocked_exact_usernames=DEFAULT_BLOCKED_EXACT_USERNAMES if raw_users is None else tuple(p.lower() for p in _split_csv(raw_users)),
        blocked_user_ids=DEFAULT_BLOCKED_USER_IDS if raw_ids is None else tuple(int(p) for p in _split_csv(raw_ids, strip_at=False)),
    )

def _match_brand_token(
    compact_fields: tuple[tuple[str, str], ...], blocked_brand_tokens: Sequence[str]
) -> Optional[str]:
    for btok in blocked_brand_tokens:
        clean_b = _compact_latin(btok)
        if clean_b:
            for label, value in compact_fields:
                if clean_b in value:
                    return f"{label}:{clean_b}"
    return None

def is_excluded_juma_recipient(
    username: Optional[str],
    *,
    user_id: Optional[int] = None,
    blocked_username_tokens: Sequence[str] = DEFAULT_BLOCKED_USERNAME_TOKENS,
    blocked_brand_tokens: Sequence[str] = DEFAULT_BLOCKED_BRAND_TOKENS,
    blocked_exact_usernames: Sequence[str] = DEFAULT_BLOCKED_EXACT_USERNAMES,
    blocked_user_ids: Sequence[int] = DEFAULT_BLOCKED_USER_IDS,
    full_name: Optional[str] = None,
    company_or_bio: Optional[str] = None,
    excluded_names: Sequence[str] = (),
) -> tuple[bool, str]:
    """ID, username, raqib brend nomi yoki istisno roʻyxati boʻyicha filtrlaydi."""
    if user_id is not None and user_id in blocked_user_ids:
        return True, f"user_id:{user_id}"
    uname = (username or "").strip().lstrip("@").lower()
    if uname:
        if uname in {(u or "").strip().lstrip("@").lower() for u in blocked_exact_usernames if (u or "").strip()}:
            return True, f"exact_username:{uname}"
        for tok in blocked_username_tokens:
            clean_tok = (tok or "").strip().lstrip("@").lower()
            if clean_tok and clean_tok in uname:
                return True, f"username:{clean_tok}"
    brand_hit = _match_brand_token(
        (("brand_username", _compact_latin(uname)), ("brand_name", _compact_latin(full_name)), ("brand_meta", _compact_latin(company_or_bio))),
        blocked_brand_tokens,
    )
    if brand_hit:
        return True, brand_hit
    name_low = (full_name or "").strip().lower()
    for excl in excluded_names if name_low else ():
        clean_excl = (excl or "").strip().lower()
        if clean_excl and clean_excl in name_low:
            return True, f"name:{excl}"
    return False, ""

def is_excluded_member(
    member: Mapping[str, object], config: JumaRateConfig, *, excluded_names: Sequence[str] = ()
) -> tuple[bool, str]:
    """Aʼzo lugʻatini configdagi barcha blok roʻyxatlariga nisbatan tekshiradi."""
    meta = " ".join(str(member.get(k) or "") for k in ("company", "bio") if member.get(k)).strip() or None
    return is_excluded_juma_recipient(
        str(member.get("username") or "") or None,
        user_id=_parse_int_id(member.get("id")),
        blocked_username_tokens=config.blocked_username_tokens,
        blocked_brand_tokens=config.blocked_brand_tokens,
        blocked_exact_usernames=config.blocked_exact_usernames,
        blocked_user_ids=config.blocked_user_ids,
        full_name=str(member.get("name") or "") or None,
        company_or_bio=meta,
        excluded_names=excluded_names,
    )

def select_target_groups(target_spec: str = "TN7", groups: Sequence[dict] = GROUP_PRIORITY) -> list[dict]:
    """Guruh kodi yoki ID boʻyicha maqsad guruhlarni tanlaydi (masalan TN7, -1003926176795, all)."""
    spec = (target_spec or "TN7").strip()
    if spec.lower() == "all":
        return list(groups)
    selected: list[dict] = []
    seen_ids: set[int] = set()
    for token in (p.strip().upper() for p in spec.split(",") if p.strip()):
        norm = f"TN{token}" if token.isdigit() else token
        matched = False
        for grp in groups:
            if norm in {str(grp.get("code", "")).upper(), str(grp.get("label", "")).upper(), str(grp["id"])}:
                matched = True
                if grp["id"] not in seen_ids:
                    selected.append(grp)
                    seen_ids.add(grp["id"])
        if not matched and token.startswith("-") and token[1:].isdigit():
            cid = int(token)
            if cid not in seen_ids:
                selected.append({"label": f"Group {cid}", "code": str(cid), "names": [], "id": cid})
                seen_ids.add(cid)
    return selected


def match_group_dialogs(dialogs: Sequence[object], group: Mapping[str, object]) -> list[object]:
    """Avval aniq chat ID, topilmasa sarlavha boʻyicha guruh dialoglarini tanlaydi."""
    exact = [d for d in dialogs if getattr(d, "id", None) == group.get("id")]
    if exact:
        return exact
    names_low = {str(n).strip().lower() for n in group.get("names", ()) if str(n).strip()}
    if not names_low:
        return []
    return [d for d in dialogs if (getattr(d, "title", None) or "").strip().lower() in names_low]

def classify_and_order_recipients(members: Sequence[dict], *, cold_limit: Optional[int]) -> tuple[list[dict], list[dict]]:
    """Issiq (oldin DM bor/mutual) aʼzolarni oldinga qoʻyadi, sovuqlarni limitlaydi."""
    warm = [m for m in members if bool(m.get("warm")) or bool(m.get("mutual"))]
    cold = [m for m in members if not (bool(m.get("warm")) or bool(m.get("mutual")))]
    if cold_limit is None:
        return warm + cold, []
    cap = max(0, cold_limit)
    return warm + cold[:cap], cold[cap:]

def _as_tashkent(now: datetime) -> datetime:
    return now.replace(tzinfo=TASHKENT_TZ) if now.tzinfo is None else now.astimezone(TASHKENT_TZ)

def is_juma_send_window(now: datetime, config: JumaRateConfig) -> bool:
    """Payshanba Shomdan Juma Shomigacha boʻlgan oynani tekshiradi."""
    local = _as_tashkent(now)
    shom = local.replace(hour=config.shom_hour, minute=config.shom_minute, second=0, microsecond=0)
    return (local >= shom) if local.weekday() == 3 else (local < shom if local.weekday() == 4 else False)

def compute_juma_deadline(now: datetime, config: JumaRateConfig) -> datetime:
    """Joriy haftaning Juma Shom vaqtini (Toshkent) qaytaradi."""
    local = _as_tashkent(now)
    friday = local + timedelta(days=(4 - local.weekday()) % 7)
    return friday.replace(hour=config.shom_hour, minute=config.shom_minute, second=0, microsecond=0)

def _quiet_end_datetime(local: datetime, config: JumaRateConfig) -> Optional[datetime]:
    start_t, end_t = time(*config.quiet_start), time(*config.quiet_end)
    if start_t == end_t:
        return None
    cur_t = local.time()
    if start_t > end_t:
        if cur_t >= start_t:
            return (local + timedelta(days=1)).replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0)
        return local.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0) if cur_t < end_t else None
    return local.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0) if start_t <= cur_t < end_t else None

def is_quiet_hours(now: datetime, config: JumaRateConfig) -> bool:
    """Tungi sokin soatlar ichida ekanligini tekshiradi."""
    return _quiet_end_datetime(_as_tashkent(now), config) is not None

def seconds_until_quiet_ends(now: datetime, config: JumaRateConfig) -> float:
    """Sokin soatlar tugashigacha qolgan soniyalarni qaytaradi."""
    local = _as_tashkent(now)
    end_dt = _quiet_end_datetime(local, config)
    return 0.0 if end_dt is None else max(0.0, (end_dt - local).total_seconds())

def is_silent_send_time(now: datetime, config: JumaRateConfig) -> bool:
    """Erta tongda (06:00–08:00) ovozsiz yuborish kerakligini aniqlaydi."""
    local = _as_tashkent(now)
    if is_quiet_hours(local, config):
        return False
    start_t, until_t = time(*config.quiet_end), time(*config.silent_until)
    if start_t >= until_t:
        return False
    return start_t <= local.time() < until_t

def next_delay_seconds(sent_count: int, config: JumaRateConfig, rng: Optional[random.Random] = None) -> tuple[float, bool]:
    """Keyingi kutish vaqtini qaytaradi; har batch_size da katta tanaffus beradi."""
    gen = rng or random
    if sent_count > 0 and config.batch_size > 0 and sent_count % config.batch_size == 0:
        return gen.uniform(config.batch_pause_min_sec, config.batch_pause_max_sec), True
    return gen.uniform(config.delay_min_sec, config.delay_max_sec), False

def estimate_duration_minutes(count: int, config: JumaRateConfig) -> float:
    """Berilgan aʼzolar soni uchun taxminiy davomiylikni (daqiqada) hisoblaydi."""
    if count <= 0:
        return 0.0
    waits = max(0, count - 1)
    batch_pauses = waits // config.batch_size if config.batch_size > 0 else 0
    avg_normal = (config.delay_min_sec + config.delay_max_sec) / 2.0
    avg_batch = (config.batch_pause_min_sec + config.batch_pause_max_sec) / 2.0
    avg_typing = (config.typing_min_sec + config.typing_max_sec) / 2.0
    return ((waits - batch_pauses) * avg_normal + batch_pauses * avg_batch + count * avg_typing) / 60.0

def load_custom_greetings(path: Optional[Path]) -> dict[str, str]:
    """Individual tabrik matnlari saqlangan JSON faylni oʻqiydi."""
    if path is None or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    greetings: dict[str, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            norm_key = str(key).strip().lstrip("@").lower()
            if isinstance(value, str) and value.strip() and norm_key:
                greetings[norm_key] = value.strip()
    elif isinstance(data, list):
        for item in data:
            text = item.get("message") or item.get("text") if isinstance(item, dict) else None
            if not isinstance(text, str) or not text.strip():
                continue
            if item.get("id") is not None:
                greetings[str(item["id"]).strip()] = text.strip()
            uname = str(item.get("username") or "").strip().lstrip("@").lower()
            if uname:
                greetings[uname] = text.strip()
    return greetings

def pick_greeting_text(
    member: Mapping[str, object], custom_greetings: Mapping[str, str], templates: Sequence[str], rng: Optional[random.Random] = None
) -> str:
    """Aʼzo uchun individual JSON matnini yoki zaxira shablonni tanlaydi."""
    uid = str(member["id"]).strip() if member.get("id") is not None else ""
    if uid and uid in custom_greetings:
        return custom_greetings[uid]
    uname = str(member.get("username") or "").strip().lstrip("@").lower()
    if uname and uname in custom_greetings:
        return custom_greetings[uname]
    return (rng or random).choice(templates)
