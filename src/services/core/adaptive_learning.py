"""Oisha-OS oʻz-oʻzini rivojlantirish va oʻrganishni birlashtiruvchi kesh va qoʻngʻiroq darsi qatlami."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 300.0
_CALL_LEARN_COOLDOWN_SEC = 180.0
_ADAPTIVE_CACHE: Dict[Tuple[int, str], Tuple[float, str]] = {}
_SEEN_CALL_DIGESTS: List[str] = []
_LAST_CALL_LEARN_BY_DB: Dict[int, float] = {}
_ENSURED_LEARNING_DBS: set[int] = set()


def reset_adaptive_cache() -> None:
    """Testlar va skill qarorlaridan keyin keshni tozalash."""
    _ADAPTIVE_CACHE.clear()
    _SEEN_CALL_DIGESTS.clear()
    _LAST_CALL_LEARN_BY_DB.clear()
    _ENSURED_LEARNING_DBS.clear()


def resolve_runtime_db(db: Any = None) -> Any:
    """Faol DB obyektini aniqlaydi; topilmasa None qaytaradi."""
    if db is not None:
        return db
    try:
        from src.context import app_ctx

        return getattr(app_ctx, "db", None)
    except Exception:
        return None


def _clip_lines(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    lines: List[str] = []
    used = 0
    for line in clean.splitlines():
        extra = len(line) + (1 if lines else 0)
        if used + extra > max_chars:
            break
        lines.append(line)
        used += extra
    if lines:
        return "\n".join(lines).strip()
    return clean[: max(0, max_chars - 1)].rstrip() + "…"


def _resolve_gemini_api_key(explicit: str = "") -> str:
    if explicit:
        return explicit
    try:
        from src.settings import settings

        secret = getattr(settings, "GEMINI_API_KEY", None)
        if secret is None:
            return ""
        return secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
    except Exception:
        return ""


async def _ensure_learning_schema(engine: Any, db: Any) -> None:
    key = id(db)
    if key in _ENSURED_LEARNING_DBS:
        return
    await engine.ensure_tables()
    _ENSURED_LEARNING_DBS.add(key)


async def get_adaptive_prompt_context(
    category: Optional[str] = None,
    db: Any = None,
    *,
    max_chars: int = 550,
) -> str:
    """Tasdiqlangan skilllar va oʻrganilgan darslardan ixcham prompt konteksti."""
    target_db = resolve_runtime_db(db)
    if target_db is None or max_chars <= 0:
        return ""

    cache_key = (id(target_db), category or "*")
    now = time.monotonic()
    cached = _ADAPTIVE_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL_SEC:
        return _clip_lines(cached[1], max_chars)

    parts: List[str] = []
    try:
        from src.services.core.self_learning import SelfLearningEngine

        engine = SelfLearningEngine(target_db, _resolve_gemini_api_key())
        await _ensure_learning_schema(engine, target_db)
        lessons = await engine.get_relevant_lessons("", category=category, limit=4)
        strategies = await engine.get_active_strategies()
        learning_text = engine.build_learning_context(lessons, strategies)
        if learning_text:
            parts.append(learning_text)
    except Exception as exc:
        logger.debug("[ADAPTIVE] Learning context skipped: %s", exc)

    try:
        from src.services.core.skill_learner import get_active_skills_context

        skills_text = await get_active_skills_context(db=target_db, limit=3)
        if skills_text:
            parts.append(skills_text)
    except Exception as exc:
        logger.debug("[ADAPTIVE] Active skills context skipped: %s", exc)

    combined = "\n".join(parts).strip()
    _ADAPTIVE_CACHE[cache_key] = (now, combined)
    return _clip_lines(combined, max_chars)


def _format_call_digest(
    analysis: Dict[str, Any],
    *,
    duration_seconds: int,
    summary: str,
    manager_name: str,
) -> str:
    weaknesses = analysis.get("zaif_tomonlar") or []
    strengths = analysis.get("kuchli_tomonlar") or []
    objections = analysis.get("etirozlar") or []
    advice = str(analysis.get("konversiya_tavsiyalari") or "").strip()
    lines = [
        f"Menejer: {manager_name or 'Nomaʼlum'} | Davomiylik: {int(duration_seconds or 0)}s | Ball: {int(analysis.get('sifat_bahosi') or 0)}/10",
        f"Natija: {analysis.get('natija') or 'nomaʼlum'} | Mijoz kayfiyati: {analysis.get('client_mood') or 'nomaʼlum'}",
    ]
    if summary:
        lines.append(f"Mazmun: {summary.strip()}")
    if strengths:
        lines.append("Kuchli tomonlar: " + "; ".join(str(x) for x in strengths[:3]))
    if weaknesses:
        lines.append("Zaif tomonlar: " + "; ".join(str(x) for x in weaknesses[:3]))
    if objections:
        lines.append("Eʼtirozlar: " + "; ".join(str(x) for x in objections[:3]))
    if advice:
        lines.append(f"Tavsiya: {advice}")
    return "\n".join(lines)


async def _extract_and_persist_call_lesson(
    target_db: Any,
    digest_text: str,
    digest_hash: str,
    analysis: Dict[str, Any],
    manager_name: str,
    *,
    router: Any,
    api_key: str,
) -> List[Dict[str, Any]]:
    from src.services.core.self_learning import SelfLearningEngine

    engine = SelfLearningEngine(
        target_db,
        _resolve_gemini_api_key(api_key),
        router=router,
    )
    await _ensure_learning_schema(engine, target_db)
    saved = await engine.extract_lessons(
        conversation=digest_text,
        client_type=str(analysis.get("category") or "call"),
        outcome=str(analysis.get("natija") or "unknown"),
        manager_name=manager_name,
    )
    _LAST_CALL_LEARN_BY_DB[id(target_db)] = time.monotonic()
    _SEEN_CALL_DIGESTS.append(digest_hash)
    if len(_SEEN_CALL_DIGESTS) > 200:
        del _SEEN_CALL_DIGESTS[:-100]
    if saved:
        _ADAPTIVE_CACHE.clear()
    return saved


async def record_call_lesson_if_notable(
    analysis: Optional[Dict[str, Any]],
    *,
    duration_seconds: int = 0,
    summary: str = "",
    manager_name: str = "",
    db: Any = None,
    router: Any = None,
    api_key: str = "",
) -> List[Dict[str, Any]]:
    """Muhim qoʻngʻiroq tahlilidan takrorlanmaydigan savdo darsini yozib boradi."""
    target_db = resolve_runtime_db(db)
    if target_db is None or not isinstance(analysis, dict) or not analysis:
        return []
    score = int(analysis.get("sifat_bahosi") or 0)
    if int(duration_seconds or 0) < 90 and score <= 0:
        return []
    digest_text = _format_call_digest(
        analysis, duration_seconds=duration_seconds, summary=summary, manager_name=manager_name
    )
    if len(digest_text) < 80:
        return []
    digest_hash = hashlib.sha256(digest_text.encode("utf-8")).hexdigest()[:16]
    if digest_hash in _SEEN_CALL_DIGESTS:
        return []
    if router is None and (time.monotonic() - _LAST_CALL_LEARN_BY_DB.get(id(target_db), 0.0)) < _CALL_LEARN_COOLDOWN_SEC:
        return []
    try:
        return await _extract_and_persist_call_lesson(
            target_db, digest_text, digest_hash, analysis, manager_name, router=router, api_key=api_key
        )
    except Exception as exc:
        logger.debug("[ADAPTIVE] Call lesson extraction failed: %s", exc)
        return []


def is_owner_user(user: Any) -> bool:
    """Xabar egasi (Owner) ekanini ID yoki username orqali tekshiradi."""
    if user is None:
        return False
    uid = getattr(user, "id", None)
    try:
        uid_int = int(uid) if uid is not None else 0
    except (TypeError, ValueError):
        uid_int = 0
    owner_ids = set()
    try:
        import os
        from src.settings import settings

        for candidate in (
            getattr(settings, "OWNER_ID", 0),
            os.getenv("OWNER_ID", "0"),
            os.getenv("TELEGRAM_OWNER_ID", "0"),
        ):
            val = int(candidate or 0)
            if val > 0:
                owner_ids.add(val)
    except Exception:
        pass
    if uid_int and uid_int in owner_ids:
        return True
    uname = (getattr(user, "username", None) or "").lstrip("@").lower()
    return uname in {"baxtiyorgaziyev", "baxtiyorjongaziyev"}


async def _store_owner_rule(
    target_db: Any,
    *,
    pattern: str,
    lesson: str,
    strategy: str,
    category: str,
    user_id: Optional[int],
    chat_id: Optional[int],
) -> None:
    from src.services.core.self_learning import SelfLearningEngine
    from src.time_utils import get_local_now

    engine = SelfLearningEngine(target_db, _resolve_gemini_api_key())
    await _ensure_learning_schema(engine, target_db)
    now = get_local_now().isoformat()
    async with await target_db.get_connection() as conn:
        await engine._upsert_lesson(
            conn,
            {
                "pattern": pattern,
                "lesson": lesson,
                "strategy": strategy,
                "confidence": 0.95,
                "category": category,
            },
            chat_id=chat_id,
            user_id=user_id,
            now=now,
        )
        cur = await conn.execute(
            "SELECT id FROM strategy_rules WHERE rule = ? AND active = 1 LIMIT 1",
            (strategy,),
        )
        if await cur.fetchone() is None:
            await conn.execute(
                "INSERT INTO strategy_rules (rule, trigger_condition, weight, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (strategy, f"owner:{category}", 0.95, now, now),
            )
        await conn.commit()
    _ADAPTIVE_CACHE.clear()


async def record_owner_feedback_rule(
    text: str,
    *,
    user_id: Optional[int] = None,
    speaker: str = "Owner",
    chat_id: Optional[int] = None,
    db: Any = None,
    router: Any = None,
) -> Optional[Dict[str, str]]:
    """Ownerʼning uslub/jarayon haqidagi izohidan darhol doimiy qoida chiqaradi."""
    target_db = resolve_runtime_db(db)
    clean = " ".join((text or "").split()).strip()
    if target_db is None or len(clean) < 6:
        return None
    low = clean.lower()
    rule: Optional[Dict[str, str]] = None
    if any(k in low for k in ("qisqa", "odamdek", "odamga o", "loʻnda", "londa", "shablon", "robot", "uzun yoz")):
        rule = {
            "pattern": "Qisqa va tabiiy uslub",
            "lesson": "Javoblar 1–3 qisqa gapdan oshmasin; odamdek loʻnda gapir, rasmiy maqtov va shablonlarni olib tashla.",
            "strategy": "1–3 qisqa gapda odamdek javob ber; hamdu sano, ortiqcha salom va shablon maqtov yozma.",
            "category": "tone",
        }
    elif any(k in low for k in ("man aytgandim", "men aytgandim", "amas", "emas", "amocrm", "moizvonki", "airtable", "faqat", "eslab qol")):
        rule = {
            "pattern": f"Owner tuzatishi ({speaker[:20]})",
            "lesson": clean[:240],
            "strategy": clean[:240],
            "category": "sales",
        }
    if rule is None:
        return None
    try:
        await _store_owner_rule(target_db, user_id=user_id, chat_id=chat_id, **rule)
        return rule
    except Exception as exc:
        logger.debug("[ADAPTIVE] Owner feedback store failed: %s", exc)
        return None
