"""Skill Learner — Ownerʼning Telegram harakatlaridan skill oʻrganish (Shadow rejim)."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 500
MIN_ACTIONS_TO_MINE = int(os.getenv("SKILL_LEARNER_MIN_ACTIONS", "30"))
MINE_BATCH = 200
MINE_INTERVAL_SECONDS = int(os.getenv("SKILL_LEARNER_INTERVAL_SECONDS", str(6 * 3600)))
SKILLS_DIR = Path(os.getenv("SKILL_LEARNER_DIR", "data/learned_skills"))

_CREATE_ACTIONS = (
    "CREATE TABLE IF NOT EXISTS owner_actions ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, chat_kind TEXT, "
    "text TEXT, reply_to_text TEXT, processed INTEGER DEFAULT 0, created_at TEXT)"
)
_CREATE_SKILLS = (
    "CREATE TABLE IF NOT EXISTS learned_skills ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, trigger TEXT, steps TEXT, "
    "example TEXT, status TEXT DEFAULT 'pending', created_at TEXT, decided_at TEXT)"
)

_ensured: Set[int] = set()


def is_enabled() -> bool:
    return os.getenv("ENABLE_SKILL_LEARNER", "1").strip().lower() in {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _row_get(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]


def _get_db(db: Any = None) -> Any:
    if db is not None:
        return db
    from src.context import app_ctx
    return getattr(app_ctx, "db", None)


async def _conn(db: Any) -> Any:
    db = _get_db(db)
    if db is None:
        return None
    conn = await _maybe_await(db.get_connection())
    if conn is None:
        return None
    if id(db) not in _ensured:
        await _maybe_await(conn.execute(_CREATE_ACTIONS))
        await _maybe_await(conn.execute(_CREATE_SKILLS))
        await _maybe_await(conn.commit())
        _ensured.add(id(db))
    return conn


async def _fetchall(conn: Any, sql: str, params: tuple = ()) -> List[Any]:
    cursor = await _maybe_await(conn.execute(sql, params))
    return list(await _maybe_await(cursor.fetchall()) or [])


def reset_schema_cache() -> None:
    """Testlar uchun."""
    _ensured.clear()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:60] or "skill"


# ---------------------------------------------------------------------------
# 1. Yozib olish
# ---------------------------------------------------------------------------

async def record_owner_action(event: Any, db: Any = None) -> bool:
    """Owner'ning chiquvchi xabarini saqlaydi. Fail-soft."""
    if not is_enabled():
        return False
    try:
        text = (getattr(event, "raw_text", None) or "").strip()
        if not text or text.startswith("/"):
            return False
        chat_id = getattr(event, "chat_id", None)
        if chat_id is not None and chat_id == getattr(event, "sender_id", object()):
            return False  # Saved Messages — shaxsiy qaydlar o'rganilmaydi
        if getattr(event, "is_private", False):
            chat_kind = "private"
        elif getattr(event, "is_group", False):
            chat_kind = "group"
        else:
            chat_kind = "channel"
        reply_text = ""
        if getattr(event, "is_reply", False):
            try:
                reply = await event.get_reply_message()
                reply_text = (getattr(reply, "raw_text", "") or "")[:MAX_TEXT_CHARS]
            except Exception:
                reply_text = ""
        conn = await _conn(db)
        if conn is None:
            return False
        await _maybe_await(conn.execute(
            "INSERT INTO owner_actions (chat_id, chat_kind, text, reply_to_text, processed, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (str(getattr(event, "chat_id", "")), chat_kind, text[:MAX_TEXT_CHARS], reply_text, _now()),
        ))
        await _maybe_await(conn.commit())
        return True
    except Exception as exc:
        logger.warning("[SKILL_LEARNER] Harakat yozilmadi: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 2. Skill qazib olish
# ---------------------------------------------------------------------------

_SYSTEM = (
    "Sen Oisha — Jon Branding Agency egasining shaxsiy AI COO'sisan. "
    "Senga egasining Telegramdagi xabarlari beriladi. Vazifang: takrorlanuvchi "
    "ish naqshlarini (qanday savolga qanday javob beradi, qanday vazifani qanday "
    "bajaradi, qaysi uslubda yozadi) topib, qayta ishlatiladigan skill qilib berish. "
    "Faqat kamida 2 marta takrorlangan naqshni ol. Shaxsiy ma'lumot, parol, karta "
    "raqami, telefon raqamini skillga yozma. Faqat JSON qaytar."
)

_PROMPT = """Mavjud skill nomlari (takrorlama): {existing}

Egasining xabarlari (har qatorda: [chat turi] <javob berilgan xabar> => egasi yozgani):
{actions}

JSON massiv qaytar, maksimal 3 ta element:
[{{"name": "qisqa nom", "trigger": "qachon ishlatiladi", "steps": ["1-qadam", "2-qadam"], "example": "namunaviy javob"}}]
Naqsh topilmasa: []"""


def parse_skill_drafts(raw: str) -> List[Dict[str, Any]]:
    """LLM javobidan skill qoralamalarini ajratadi."""
    if not raw:
        return []
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    drafts: List[Dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        trigger = str(item.get("trigger") or "").strip()
        steps = item.get("steps") or []
        if isinstance(steps, str):
            steps = [steps]
        steps = [str(s).strip() for s in steps if str(s).strip()]
        if not name or not trigger or not steps:
            continue
        drafts.append({
            "name": name[:80],
            "trigger": trigger[:300],
            "steps": steps[:10],
            "example": str(item.get("example") or "").strip()[:500],
        })
    return drafts[:3]


def _format_actions(rows: List[Any]) -> str:
    lines = []
    for row in rows:
        kind = _row_get(row, "chat_kind", 1) or "?"
        text = (_row_get(row, "text", 2) or "").replace("\n", " ")
        reply = (_row_get(row, "reply_to_text", 3) or "").replace("\n", " ")
        lines.append(f"[{kind}] <{reply[:200]}> => {text[:300]}" if reply else f"[{kind}] => {text[:300]}")
    return "\n".join(lines)


async def mine_skills(db: Any = None, router: Any = None) -> List[int]:
    """Yangi harakatlardan skill qoralamalari yaratadi. Yangi skill id'larini qaytaradi."""
    conn = await _conn(db)
    if conn is None:
        return []
    rows = await _fetchall(
        conn,
        "SELECT id, chat_kind, text, reply_to_text FROM owner_actions "
        "WHERE processed = 0 ORDER BY id DESC LIMIT ?",
        (MINE_BATCH,),
    )
    if len(rows) < MIN_ACTIONS_TO_MINE:
        return []

    existing = [
        _row_get(r, "name", 0)
        for r in await _fetchall(conn, "SELECT name FROM learned_skills WHERE status != 'rejected'")
    ]
    if router is None:
        from src.services.utils.free_ai_router import get_free_ai_router
        router = get_free_ai_router()
    prompt = _PROMPT.format(
        existing=", ".join(existing) or "yo'q",
        actions=_format_actions(list(reversed(rows))),
    )
    try:
        result = await router.generate_text(prompt, system=_SYSTEM, max_tokens=1500, temperature=0.2)
        drafts = parse_skill_drafts(getattr(result, "text", "") or "")
    except Exception as exc:
        logger.warning("[SKILL_LEARNER] LLM xatosi, keyinroq qayta uriniladi: %s", exc)
        return []

    existing_slugs = {slugify(n) for n in existing}
    new_ids: List[int] = []
    for draft in drafts:
        if slugify(draft["name"]) in existing_slugs:
            continue
        cursor = await _maybe_await(conn.execute(
            "INSERT INTO learned_skills (name, trigger, steps, example, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (draft["name"], draft["trigger"], json.dumps(draft["steps"], ensure_ascii=False), draft["example"], _now()),
        ))
        new_id = getattr(cursor, "lastrowid", None)
        if new_id is None:
            id_rows = await _fetchall(
                conn, "SELECT id FROM learned_skills WHERE name = ? ORDER BY id DESC LIMIT 1", (draft["name"],)
            )
            if id_rows:
                new_id = _row_get(id_rows[0], "id", 0)
        if new_id is not None:
            new_ids.append(int(new_id))
        existing_slugs.add(slugify(draft["name"]))

    max_id = max(int(_row_get(r, "id", 0)) for r in rows)
    await _maybe_await(conn.execute("UPDATE owner_actions SET processed = 1 WHERE id <= ?", (max_id,)))
    await _maybe_await(conn.commit())
    logger.info("[SKILL_LEARNER] %d harakatdan %d yangi skill qoralamasi", len(rows), len(new_ids))
    return new_ids


# ---------------------------------------------------------------------------
# 3. Owner tasdig'i
# ---------------------------------------------------------------------------

async def _get_skill(conn: Any, skill_id: int) -> Optional[Dict[str, Any]]:
    rows = await _fetchall(
        conn,
        "SELECT id, name, trigger, steps, example, status FROM learned_skills WHERE id = ?",
        (skill_id,),
    )
    if not rows:
        return None
    row = rows[0]
    keys = ("id", "name", "trigger", "steps", "example", "status")
    skill = {k: _row_get(row, k, i) for i, k in enumerate(keys)}
    try:
        skill["steps"] = json.loads(skill["steps"] or "[]")
    except (TypeError, json.JSONDecodeError):
        skill["steps"] = [str(skill["steps"])]
    return skill


def format_skill_card(skill: Dict[str, Any]) -> str:
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(skill.get("steps") or [], 1))
    ex = f"Namuna: {skill['example']}\n" if skill.get("example") else ""
    return (
        f"🧠 Yangi skill #{skill['id']}: {skill['name']}\n"
        f"Qachon: {skill['trigger']}\nQadamlar:\n{steps}\n{ex}"
        f"\n/skill_ok {skill['id']} — tasdiqlash\n/skill_no {skill['id']} — rad etish"
    )


def render_skill_md(skill: Dict[str, Any]) -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(skill.get("steps") or [], 1))
    example = f"\n## Namuna\n\n{skill['example']}\n" if skill.get("example") else ""
    return (
        f"---\nname: {slugify(skill['name'])}\ndescription: {skill['trigger']}\n"
        f"source: owner-telegram-actions\n---\n\n# {skill['name']}\n\n"
        f"**Qachon:** {skill['trigger']}\n\n## Qadamlar\n\n{steps}\n{example}"
    )


async def decide_skill(skill_id: int, approve: bool, db: Any = None) -> Optional[Dict[str, Any]]:
    """Skillni tasdiqlaydi yoki rad etadi. Tasdiqlansa SKILL.md yoziladi."""
    conn = await _conn(db)
    if conn is None:
        return None
    skill = await _get_skill(conn, skill_id)
    if skill is None or skill["status"] != "pending":
        return skill
    status = "active" if approve else "rejected"
    await _maybe_await(conn.execute(
        "UPDATE learned_skills SET status = ?, decided_at = ? WHERE id = ?",
        (status, _now(), skill_id),
    ))
    await _maybe_await(conn.commit())
    skill["status"] = status
    try:
        from src.services.core.adaptive_learning import reset_adaptive_cache

        reset_adaptive_cache()
    except Exception:
        pass
    if approve:
        try:
            path = SKILLS_DIR / slugify(skill["name"]) / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_skill_md(skill), encoding="utf-8")
        except OSError as exc:
            logger.warning("[SKILL_LEARNER] SKILL.md yozilmadi: %s", exc)
    return skill


async def list_skills(db: Any = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = await _conn(db)
    if conn is None:
        return []
    sql = "SELECT id FROM learned_skills"
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    ids = [int(_row_get(r, "id", 0)) for r in await _fetchall(conn, sql + " ORDER BY id", params)]
    return [s for s in [await _get_skill(conn, i) for i in ids] if s]


async def get_active_skills_context(db: Any = None, limit: int = 10) -> str:
    """Tasdiqlangan skilllar — AI prompt'iga kontekst sifatida qo'shish uchun."""
    skills = (await list_skills(db, status="active"))[-limit:]
    if not skills:
        return ""
    parts = ["Egasining tasdiqlangan ish uslublari (skilllar):"]
    for s in skills:
        parts.append(f"- {s['name']} — qachon: {s['trigger']}; qadamlar: " + "; ".join(s["steps"]))
    return "\n".join(parts)


_CMD_RE = re.compile(r"^/(skills|skill_ok|skill_no)(?:\s+(\d+))?\s*$")


async def handle_skill_command(event: Any, db: Any = None) -> bool:
    """Saved Messagesʼdagi /skills, /skill_ok <id>, /skill_no <id> buyruqlari."""
    match = _CMD_RE.match((getattr(event, "raw_text", "") or "").strip())
    if not match:
        return False
    cmd, raw_id = match.group(1), match.group(2)
    if cmd == "skills":
        skills = await list_skills(db)
        if not skills:
            await event.reply("🧠 Hali skill oʻrganilmagan.")
            return True
        icons = {"pending": "⏳", "active": "✅", "rejected": "❌"}
        lines = [f"{icons.get(s['status'], '•')} #{s['id']} {s['name']}" for s in skills[-30:]]
        await event.reply("🧠 Skilllar:\n" + "\n".join(lines))
        return True
    if not raw_id:
        await event.reply(f"Foydalanish: /{cmd} <id>")
        return True
    skill = await decide_skill(int(raw_id), approve=(cmd == "skill_ok"), db=db)
    if skill is None:
        await event.reply(f"Skill #{raw_id} topilmadi.")
    elif cmd == "skill_ok":
        await event.reply(f"✅ Skill #{raw_id} faol: {skill['name']}")
    else:
        await event.reply(f"❌ Skill #{raw_id} rad etildi.")
    return True


async def skill_learner_loop(
    client: Any,
    db: Any = None,
    bot_runtime: Any = None,
    owner_id: Optional[int] = None,
) -> None:
    """Davriy qazib olish va yangi qoralamalarni Ownerʼga yuborish."""
    from src.services.core.skill_learner_bot import run_skill_learner_loop

    await run_skill_learner_loop(client=client, db=db, bot_runtime=bot_runtime, owner_id=owner_id)
