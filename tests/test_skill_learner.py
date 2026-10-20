import sqlite3
from types import SimpleNamespace

import pytest

from src.services.core import skill_learner as sl


class FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def get_connection(self):
        return self.conn


class FakeEvent:
    def __init__(self, text, chat_id=100, sender_id=1, reply_text=None):
        self.raw_text = text
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.is_private = True
        self.is_group = False
        self.is_reply = reply_text is not None
        self._reply_text = reply_text
        self.replies = []

    async def get_reply_message(self):
        return SimpleNamespace(raw_text=self._reply_text)

    async def reply(self, text):
        self.replies.append(text)


class FakeRouter:
    def __init__(self, text):
        self.text = text

    async def generate_text(self, prompt, **kwargs):
        self.prompt = prompt
        return SimpleNamespace(text=self.text)


@pytest.fixture
def db(tmp_path, monkeypatch):
    sl.reset_schema_cache()
    monkeypatch.setattr(sl, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(sl, "MIN_ACTIONS_TO_MINE", 2)
    monkeypatch.setenv("ENABLE_SKILL_LEARNER", "1")
    return FakeDB()


def test_parse_skill_drafts_filters_invalid():
    raw = 'Mana: [{"name": "Narx", "trigger": "narx so\'rasa", "steps": ["prays yubor"]}, {"name": ""}]'
    drafts = sl.parse_skill_drafts(raw)
    assert [d["name"] for d in drafts] == ["Narx"]
    assert sl.parse_skill_drafts("no json") == []


@pytest.mark.asyncio
async def test_record_skips_commands_and_saved_messages(db):
    assert await sl.record_owner_action(FakeEvent("/skills"), db) is False
    assert await sl.record_owner_action(FakeEvent("eslatma", chat_id=1, sender_id=1), db) is False
    assert await sl.record_owner_action(FakeEvent("Narxi 5 mln", reply_text="Logo qancha?"), db) is True
    rows = db.conn.execute("SELECT text, reply_to_text FROM owner_actions").fetchall()
    assert [tuple(r) for r in rows] == [("Narxi 5 mln", "Logo qancha?")]


@pytest.mark.asyncio
async def test_disabled_does_not_record(db, monkeypatch):
    monkeypatch.setenv("ENABLE_SKILL_LEARNER", "0")
    assert await sl.record_owner_action(FakeEvent("salom"), db) is False


@pytest.mark.asyncio
async def test_mine_approve_flow(db):
    for _ in range(3):
        await sl.record_owner_action(FakeEvent("Narxi 5 mln", reply_text="Logo qancha?"), db)
    router = FakeRouter('[{"name": "Logo narxi", "trigger": "logo narxi so\'ralsa", '
                        '"steps": ["5 mln deb ayt", "portfolio yubor"], "example": "Narxi 5 mln"}]')
    ids = await sl.mine_skills(db, router=router)
    assert len(ids) == 1
    assert "Logo qancha?" in router.prompt
    # Qayta ishlangan harakatlar qayta qazilmaydi
    assert await sl.mine_skills(db, router=router) == []

    event = FakeEvent(f"/skill_ok {ids[0]}", chat_id=1, sender_id=1)
    assert await sl.handle_skill_command(event, db) is True
    assert "faol" in event.replies[0]
    md = (sl.SKILLS_DIR / "logo-narxi" / "SKILL.md").read_text(encoding="utf-8")
    assert "portfolio yubor" in md
    ctx = await sl.get_active_skills_context(db)
    assert "Logo narxi" in ctx


@pytest.mark.asyncio
async def test_reject_and_duplicate_skipped(db):
    for _ in range(2):
        await sl.record_owner_action(FakeEvent("ok"), db)
    router = FakeRouter('[{"name": "Tasdiq", "trigger": "x", "steps": ["y"]}]')
    ids = await sl.mine_skills(db, router=router)
    event = FakeEvent(f"/skill_no {ids[0]}")
    await sl.handle_skill_command(event, db)
    assert "rad" in event.replies[0]
    assert await sl.get_active_skills_context(db) == ""
    assert not sl.SKILLS_DIR.exists()


@pytest.mark.asyncio
async def test_unknown_command_ignored(db):
    assert await sl.handle_skill_command(FakeEvent("/report"), db) is False
