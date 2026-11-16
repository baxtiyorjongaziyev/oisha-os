"""TDD tests for Oisha self-improvement, Turso schema repair, and adaptive learning loop."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from src.database import Database
from src.db.repositories.proposals import ProposalRepository
from src.services.core import adaptive_learning as al
from src.services.core import skill_learner as sl
from src.services.core import skill_learner_bot as slb
from src.services.core.admin_bot import handlers_callbacks
from src.services.core.agent_brain import OishaBrain
from src.services.core.checkin_composer import compose_checkin
from src.services.core.evolution_scheduler import EvolutionScheduler
from src.services.core.jamoa_ritm.brain import HamrohBrain
from src.services.core.oisha_self_diagnosis import ImprovementProposal
from src.services.core.sales_coach_reply import coach_reply
from src.services.core.self_improvement import SelfImprovementService
from src.services.core.self_learning import SelfLearningEngine
from src.services.core.telegram.aiogram_telethon_compat import AiogramLegacyCallbackEvent
from src.services.core.telegram.bot_runtime import AiogramBotRuntime


class _TursoDictCursor:
    def __init__(self, rows, cols, lastrowid=None):
        self._rows = rows
        self._cols = cols
        self.lastrowid = lastrowid

    async def fetchall(self):
        return [dict(zip(self._cols, r)) for r in self._rows]

    async def fetchone(self):
        return dict(zip(self._cols, self._rows[0])) if self._rows else None


class _TursoSimulatedConn:
    """Simulates Turso: PRAGMA returns [], pragma_table_info(?) returns dicts, no lastrowid."""

    def __init__(self, conn: aiosqlite.Connection, hide_lastrowid: bool = True):
        self._conn = conn
        self._hide_lastrowid = hide_lastrowid

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, sql: str, params=()):
        normalized = sql.strip().upper()
        if normalized.startswith("PRAGMA"):
            return _TursoDictCursor([], [])
        cur = await self._conn.execute(sql, params)
        if cur.description is None:
            return _TursoDictCursor([], [], lastrowid=None if self._hide_lastrowid else cur.lastrowid)
        cols = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return _TursoDictCursor(rows, cols, lastrowid=None if self._hide_lastrowid else cur.lastrowid)

    async def commit(self):
        await self._conn.commit()


class _TursoStubDB:
    def __init__(self, conn: aiosqlite.Connection, hide_lastrowid: bool = True):
        self._wrapper = _TursoSimulatedConn(conn, hide_lastrowid=hide_lastrowid)

    async def get_connection(self):
        return self._wrapper


@pytest.mark.asyncio
async def test_turso_pragma_mismatch_migrates_legacy_proposals_and_rebuilds_indexes(tmp_path):
    """Reproduces prod Turso failure: legacy INTEGER PK table + existing indexes + empty PRAGMA."""
    async with aiosqlite.connect(tmp_path / "turso_legacy.db") as conn:
        await conn.execute(
            """
            CREATE TABLE improvement_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT NOT NULL,
                gap TEXT NOT NULL,
                proposal TEXT NOT NULL,
                category TEXT,
                severity TEXT,
                title TEXT,
                fingerprint TEXT,
                status TEXT DEFAULT 'proposed'
            )
            """
        )
        await conn.execute("CREATE INDEX idx_proposals_status ON improvement_proposals (status)")
        await conn.execute("CREATE INDEX idx_proposals_severity ON improvement_proposals (severity)")
        await conn.execute("CREATE INDEX idx_proposals_fingerprint ON improvement_proposals (fingerprint)")
        await conn.execute(
            "INSERT INTO improvement_proposals (area, gap, proposal, category, title) "
            "VALUES ('error handling', 'eski gap', 'eski taklif', 'unknown', 'Untitled proposal')"
        )
        await conn.commit()

        repo = ProposalRepository(_TursoStubDB(conn))
        await repo.init_table()

        col_types = await repo._get_table_column_types("improvement_proposals")
        assert col_types["id"].upper() == "TEXT"
        assert "area" not in col_types

        legacy_cols = await repo._get_table_columns("agent_improvement_proposals_legacy")
        assert {"area", "gap", "proposal"}.issubset(legacy_cols)

        await repo.save_proposals([
            ImprovementProposal(
                id="DIAG-TURSO1",
                category="error_fix",
                severity="high",
                title="Yangi tashxis",
                problem="Xato aniqlandi",
                proposed_solution="Tuzatish kerak",
            )
        ])
        saved = await repo.get_proposal("DIAG-TURSO1")
        assert saved is not None and saved["title"] == "Yangi tashxis"

        idx_cur = await conn.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_proposals_%'"
        )
        idx_map = {row[0]: row[1] for row in await idx_cur.fetchall()}
        assert idx_map == {
            "idx_proposals_status": "improvement_proposals",
            "idx_proposals_severity": "improvement_proposals",
            "idx_proposals_fingerprint": "improvement_proposals",
        }


@pytest.mark.asyncio
async def test_aiogram_runtime_maps_link_preview_and_self_improvement_sends_cards(tmp_path):
    db = Database(str(tmp_path / "bot_cards.db"))
    await db.init_db()
    sent_calls = []

    class FakeAiogramBot:
        async def send_message(self, **kwargs):
            sent_calls.append(kwargs)
            return SimpleNamespace(message_id=100 + len(sent_calls))

    runtime = AiogramBotRuntime(FakeAiogramBot())
    service = SelfImprovementService(db, bot_client=runtime, owner_id=42, project_root=str(tmp_path))
    await service.ensure_ready()
    proposal = ImprovementProposal(
        id="DIAG-CARD1",
        category="feature_gap",
        severity="high",
        title="Test taklif",
        problem="Ulanmagan modul",
        proposed_solution="Ulash kerak",
    )
    await service.repository.save_proposal(proposal)

    assert await service.notify_digest([proposal]) is True
    assert sent_calls[0].get("link_preview_options") is not None or sent_calls[0].get("disable_web_page_preview") is True
    assert "link_preview" not in sent_calls[0]

    sent_count = await service.send_proposal_cards(target=42)
    assert sent_count == 1
    assert sent_calls[1].get("link_preview_options") is not None or sent_calls[1].get("disable_web_page_preview") is True
    assert sent_calls[1]["reply_markup"] is not None

    md_calls = []
    md_runtime = AiogramBotRuntime(SimpleNamespace(send_message=AsyncMock(side_effect=lambda **kw: md_calls.append(kw) or SimpleNamespace(message_id=103))))
    await md_runtime.send_message(42, "*Salom*", parse_mode="md")
    assert md_calls[0]["parse_mode"] == "Markdown"

    cb_msg = SimpleNamespace(
        text="Card text <tag>",
        chat=SimpleNamespace(id=42),
        message_id=102,
        edit_text=AsyncMock(),
        answer=AsyncMock(),
    )
    cb = SimpleNamespace(
        data="improve:accept:DIAG-CARD1",
        from_user=SimpleNamespace(id=42),
        message=cb_msg,
        answer=AsyncMock(),
    )
    await handlers_callbacks._handle_improvement_callback(
        SimpleNamespace(self_improvement=service),
        AiogramLegacyCallbackEvent(cb),
        "improve:accept:DIAG-CARD1",
    )
    cb.answer.assert_awaited_once()
    cb_msg.edit_text.assert_awaited_once()
    edited_html = cb_msg.edit_text.call_args.args[0]
    assert "&lt;tag&gt;" in edited_html
    assert "✅ AI agent uchun qabul qilindi" in edited_html
    await db.close()


@pytest.mark.asyncio
async def test_evolution_scheduler_isolates_failing_diagnosis():
    from datetime import datetime, timezone

    scheduler = EvolutionScheduler.__new__(EvolutionScheduler)
    calls = []
    scheduler._learning_engine = None
    scheduler._evolution_engine = None
    scheduler._improvement_service = SimpleNamespace(run_diagnosis=AsyncMock(side_effect=RuntimeError("db fail")))

    async def ok_synthesis():
        calls.append("synthesis")

    async def ok_metrics():
        calls.append("metrics")

    scheduler._do_synthesis = ok_synthesis
    scheduler._record_metrics_snapshot = ok_metrics
    scheduler.db = SimpleNamespace(is_job_run=AsyncMock(return_value=False), mark_job_run=AsyncMock())

    now_10am = datetime(2026, 11, 16, 10, 5, tzinfo=timezone.utc)
    last_syn, last_met = await scheduler._run_once(now_10am, None, None)

    assert calls == ["synthesis", "metrics"]
    assert last_syn == now_10am
    assert last_met == now_10am


@pytest.mark.asyncio
async def test_oisha_brain_falls_back_to_free_ai_router_when_primary_fails(monkeypatch):
    monkeypatch.delenv("GEMINI_BRAIN_MODEL", raising=False)
    brain = OishaBrain()
    assert brain.gemini_model == "gemini-2.5-flash"

    class FailingModels:
        def generate_content(self, **kwargs):
            raise RuntimeError("404 NOT_FOUND")

    brain._client = SimpleNamespace(models=FailingModels())
    brain._router = SimpleNamespace(
        generate_text=AsyncMock(
            return_value=SimpleNamespace(
                text='```json\n{"diagnosis": "Router fallback ishladi", "affected_component": "brain", "proposed_fix": "ok", "priority": "low", "safe_to_auto_apply": false, "owner_action_needed": "none"}\n```'
            )
        )
    )
    res = await brain._diagnose([{"action": "sync", "error": "timeout"}], task="check")
    assert res["diagnosis"] == "Router fallback ishladi"
    assert res["affected_component"] == "brain"


@pytest.mark.asyncio
async def test_self_learning_dedup_and_turso_dict_rows(tmp_path):
    async with aiosqlite.connect(tmp_path / "learn.db") as conn:
        fake_router = SimpleNamespace(
            generate_text=AsyncMock(
                return_value=SimpleNamespace(
                    text=json.dumps([
                        {
                            "pattern": "Narx etirozi",
                            "lesson": "Narxdan oldin qiymatni koʻrsatish kerak",
                            "strategy": "2 ta muvaffaqiyatli keys aytilsin",
                            "confidence": 0.9,
                            "category": "sales",
                        }
                    ])
                )
            )
        )
        engine = SelfLearningEngine(_TursoStubDB(conn), gemini_api_key="", router=fake_router)
        await engine.ensure_tables()

        conv = "Mijoz: Narxi qimmat ekan.\nMenejer: Keling avval foydasini koʻrib chiqaylik, keyin hisoblaymiz."
        first = await engine.extract_lessons(conv, outcome="converted", manager_name="Rayxon")
        second = await engine.extract_lessons(conv, outcome="converted", manager_name="Rayxon")
        assert len(first) == 1 and len(second) == 1

        cnt_cur = await conn.execute("SELECT COUNT(*) FROM learning_journal")
        assert (await cnt_cur.fetchone())[0] == 1

        lessons = await engine.get_relevant_lessons("", category="sales")
        assert lessons[0]["pattern"] == "Narx etirozi"


@pytest.mark.asyncio
async def test_adaptive_loop_records_call_lesson_and_injects_into_prompts(tmp_path, monkeypatch):
    al.reset_adaptive_cache()
    sl.reset_schema_cache()
    monkeypatch.setattr(sl, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(sl, "MIN_ACTIONS_TO_MINE", 2)
    monkeypatch.setenv("ENABLE_SKILL_LEARNER", "1")

    async with aiosqlite.connect(tmp_path / "adaptive.db") as conn:
        db = _TursoStubDB(conn, hide_lastrowid=True)

        # Short zero-score noise call is ignored
        ignored = await al.record_call_lesson_if_notable(
            {"sifat_bahosi": 0}, duration_seconds=12, summary="qisqa", db=db
        )
        assert ignored == []

        call_router = SimpleNamespace(
            generate_text=AsyncMock(
                return_value=SimpleNamespace(
                    text=json.dumps([
                        {
                            "pattern": "Toʻlov sanasi",
                            "lesson": "Suhbat oxirida aniq toʻlov sanasi kelishilsin",
                            "strategy": "Sana va soatni SMS bilan tasdiqlang",
                            "confidence": 0.85,
                            "category": "sales",
                        }
                    ])
                )
            )
        )
        saved = await al.record_call_lesson_if_notable(
            {
                "sifat_bahosi": 6,
                "category": "sotuv",
                "natija": "keyinga_qoldirildi",
                "zaif_tomonlar": ["Aniq sana kelishilmadi"],
                "etirozlar": ["Rahbar bilan maslahatlashaman"],
                "konversiya_tavsiyalari": "Keyingi qoʻngʻiroq vaqtini belgilang",
            },
            duration_seconds=185,
            summary="Mijoz qiziqdi lekin aniq sana belgilanmadi",
            manager_name="Rayxon",
            db=db,
            router=call_router,
        )
        assert len(saved) == 1

        # Skill mining with Turso missing lastrowid still returns IDs
        await sl.record_owner_action(SimpleNamespace(raw_text="Qisqa yozing", chat_id=10, sender_id=1, is_private=True, is_group=False, is_reply=False), db=db)
        await sl.record_owner_action(SimpleNamespace(raw_text="Oddiy tushuntiring", chat_id=11, sender_id=1, is_private=True, is_group=False, is_reply=False), db=db)
        mine_router = SimpleNamespace(
            generate_text=AsyncMock(
                return_value=SimpleNamespace(
                    text=json.dumps([{"name": "Sodda til", "trigger": "javobda", "steps": ["qisqa yoz"], "example": "Tayyor."}])
                )
            )
        )
        new_ids = await sl.mine_skills(db=db, router=mine_router)
        assert len(new_ids) == 1

        # Deliver pending skill card via Aiogram runtime + approve via inline callback
        bot_calls = []
        runtime = AiogramBotRuntime(SimpleNamespace(send_message=AsyncMock(side_effect=lambda **kw: bot_calls.append(kw) or SimpleNamespace(message_id=77))))
        sent = await slb.notify_pending_skills_to_owner(new_ids, db=db, bot_runtime=runtime, owner_id=42)
        assert sent == 1
        assert "Sodda til" in bot_calls[0]["text"]
        assert bot_calls[0]["reply_markup"] is not None

        cb_msg = SimpleNamespace(text="Skill card", edit_text=AsyncMock())
        cb = SimpleNamespace(data=f"skill:ok:{new_ids[0]}", from_user=SimpleNamespace(id=42), message=cb_msg, answer=AsyncMock())
        handled = await slb.handle_skill_callback(AiogramLegacyCallbackEvent(cb), f"skill:ok:{new_ids[0]}", owner_id=42, db=db)
        assert handled is True
        cb.answer.assert_awaited_once()
        assert "✅ Skill" in cb_msg.edit_text.call_args.args[0]

        # Wire context into checkin_composer, sales_coach_reply, and HamrohBrain
        monkeypatch.setattr(al, "resolve_runtime_db", lambda explicit=None: explicit or db)
        seen_systems = []

        async def capture_gen(prompt, **kwargs):
            seen_systems.append(kwargs["system"])
            return "Salom, Shaxboz aka bilan toʻlov sanasini bugun kelishib oling!"

        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(hours=5))
        await compose_checkin("Rayxon", datetime(2026, 11, 16, 12, 0, tzinfo=tz), None, context={}, generate=capture_gen)
        await coach_reply("Rayxon", "Mijoz oʻylab koʻraman dedi", "Oldingi xabar", generate=capture_gen)
        await HamrohBrain(generate=capture_gen, tz=tz).answer("Nima qilaylik?", [], asker="Rayxon")

        assert len(seen_systems) == 3
        for sys_prompt in seen_systems:
            assert "Sodda til" in sys_prompt or "toʻlov sanasi" in sys_prompt


@pytest.mark.asyncio
async def test_admin_skill_commands_and_owner_gate(tmp_path, monkeypatch):
    al.reset_adaptive_cache()
    sl.reset_schema_cache()
    monkeypatch.setattr(sl, "SKILLS_DIR", tmp_path / "skills")
    async with aiosqlite.connect(tmp_path / "admin_skills.db") as conn:
        db = _TursoStubDB(conn)
        await sl._conn(db)
        await conn.execute(
            "INSERT INTO learned_skills (name, trigger, steps, example, status, created_at) "
            "VALUES ('Yangi skill', 'savolda', '[\"qadam 1\"]', 'namuna', 'pending', '2026-11-16T00:00:00Z')"
        )
        await conn.commit()

        non_owner_ev = SimpleNamespace(raw_text="/skills", sender_id=99, respond=AsyncMock())
        assert await slb.handle_admin_skill_command(non_owner_ev, owner_id=42, db=db) is False
        non_owner_ev.respond.assert_not_awaited()

        sent_cards = []
        runtime = AiogramBotRuntime(SimpleNamespace(send_message=AsyncMock(side_effect=lambda **kw: sent_cards.append(kw) or SimpleNamespace(message_id=1))))
        owner_list_ev = SimpleNamespace(raw_text="/skills", sender_id=42, respond=AsyncMock())
        assert await slb.handle_admin_skill_command(owner_list_ev, owner_id=42, db=db, bot_runtime=runtime) is True
        owner_list_ev.respond.assert_awaited_once()
        assert "Yangi skill" in owner_list_ev.respond.call_args.args[0]
        assert len(sent_cards) == 1 and sent_cards[0]["reply_markup"] is not None

        ok_ev = SimpleNamespace(raw_text="/skill_ok 1", sender_id=42, respond=AsyncMock())
        assert await slb.handle_admin_skill_command(ok_ev, owner_id=42, db=db) is True
        assert "faollashtirildi" in ok_ev.respond.call_args.args[0]
        assert (tmp_path / "skills" / "yangi-skill" / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_owner_feedback_rule_persists_and_shapes_owner_and_sales_replies(tmp_path, monkeypatch):
    al.reset_adaptive_cache()
    async with aiosqlite.connect(tmp_path / "owner_feedback.db") as conn:
        db = _TursoStubDB(conn)
        rule = await al.record_owner_feedback_rule(
            "qisqa qisqa odamga o'xshab yoz",
            user_id=150074828,
            speaker="Baxtiyorjon",
            chat_id=-1003854308552,
            db=db,
        )
        assert rule is not None and rule["category"] == "tone"

        ctx = await al.get_adaptive_prompt_context(category="sales", db=db, max_chars=550)
        assert "1–3 qisqa gapda odamdek javob ber" in ctx

        monkeypatch.setattr(al, "resolve_runtime_db", lambda explicit=None: explicit or db)
        captured = {}

        async def fake_gen(prompt, **kwargs):
            captured["system"] = kwargs["system"]
            captured["prompt"] = prompt
            return "Tushundim, bundan buyon qisqa va odamdek yozaman."

        reply = await coach_reply(
            "Baxtiyorjon",
            "qisqa qisqa odamga o'xshab yoz",
            "Assalomu alaykum...",
            generate=fake_gen,
            is_owner=True,
        )
        assert reply == "Tushundim, bundan buyon qisqa va odamdek yozaman."
        assert "MUTLAQO xushomad" in captured["system"]
        assert "1–3 qisqa gapda odamdek javob ber" in captured["system"]
        assert "Rahbar (Owner): Baxtiyorjon" in captured["prompt"]


