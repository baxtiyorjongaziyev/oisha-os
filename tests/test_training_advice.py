"""Tests for the training_advice table repository methods, scheduler, and route."""
import pytest


@pytest.mark.asyncio
async def test_upsert_and_get_training_advice_round_trip():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(
        manager_id=7,
        manager_name="Test Manager",
        advice_text="E'tirozlar bosqichini mustahkamlang.",
    )

    rows = await repo.get_training_advice()

    assert len(rows) == 1
    assert rows[0]["manager_id"] == 7
    assert rows[0]["manager_name"] == "Test Manager"
    assert rows[0]["advice_text"] == "E'tirozlar bosqichini mustahkamlang."
    assert rows[0]["generated_at"]  # non-empty timestamp


@pytest.mark.asyncio
async def test_upsert_training_advice_replaces_existing_row_for_same_manager():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(manager_id=7, manager_name="Test Manager", advice_text="Old advice")
    await repo.upsert_training_advice(manager_id=7, manager_name="Test Manager", advice_text="New advice")

    rows = await repo.get_training_advice()

    assert len(rows) == 1
    assert rows[0]["advice_text"] == "New advice"


@pytest.mark.asyncio
async def test_get_training_advice_filters_by_manager_id():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(manager_id=1, manager_name="Manager One", advice_text="Advice for 1")
    await repo.upsert_training_advice(manager_id=2, manager_name="Manager Two", advice_text="Advice for 2")

    rows = await repo.get_training_advice(manager_id=1)

    assert len(rows) == 1
    assert rows[0]["manager_id"] == 1


@pytest.mark.asyncio
async def test_get_training_advice_empty_when_no_rows():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    rows = await repo.get_training_advice()

    assert rows == []


@pytest.mark.asyncio
async def test_run_training_advice_cycle_generates_advice_for_lowest_scoring_manager(monkeypatch):
    from src.schedulers import training_advice_scheduler

    async def fake_fetch_rows():
        return [
            {
                "manager_id": 1,
                "manager_name": "High Scorer",
                "overall_score": 90,
                "scores": '{"etirozlar": 85}',
                "weaknesses": "[]",
            },
            {
                "manager_id": 2,
                "manager_name": "Low Scorer",
                "overall_score": 40,
                "scores": '{"etirozlar": 20}',
                "weaknesses": '["Narx e\'tiroziga tayyor javob yo\'q"]',
            },
        ]

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    captured_prompt = {}

    class FakeProviderResult:
        text = "Sizga E'tirozlar bosqichida mashq tavsiya etiladi."

    class FakeRouter:
        async def generate_text(self, prompt, **kwargs):
            captured_prompt["value"] = prompt
            return FakeProviderResult()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.FreeAIProviderRouter",
        lambda: FakeRouter(),
    )

    written = {}

    class FakeRepo:
        async def upsert_training_advice(self, manager_id, manager_name, advice_text):
            written["manager_id"] = manager_id
            written["manager_name"] = manager_name
            written["advice_text"] = advice_text

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.get_db",
        lambda: FakeDb(),
    )

    await training_advice_scheduler.run_training_advice_cycle()

    assert written["manager_id"] == 2
    assert written["manager_name"] == "Low Scorer"
    assert written["advice_text"] == "Sizga E'tirozlar bosqichida mashq tavsiya etiladi."
    assert "Low Scorer" in captured_prompt["value"]
    assert "etirozlar" in captured_prompt["value"].lower() or "E'tirozlar" in captured_prompt["value"]


@pytest.mark.asyncio
async def test_run_training_advice_cycle_skips_when_no_call_analyses(monkeypatch):
    from src.schedulers import training_advice_scheduler

    async def fake_fetch_rows():
        return []

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    write_calls = []

    class FakeRepo:
        async def upsert_training_advice(self, *args, **kwargs):
            write_calls.append((args, kwargs))

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.get_db",
        lambda: FakeDb(),
    )

    await training_advice_scheduler.run_training_advice_cycle()

    assert write_calls == []


@pytest.mark.asyncio
async def test_training_advice_route_returns_unavailable_when_no_rows(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return []

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    result = await get_sales_quality_training_advice()

    assert result["available"] is False
    assert result["advice"] == []


@pytest.mark.asyncio
async def test_training_advice_route_returns_cached_rows(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return [
                {
                    "manager_id": 2,
                    "manager_name": "Low Scorer",
                    "advice_text": "E'tirozlar bosqichini mustahkamlang.",
                    "generated_at": "2026-09-15T00:00:00+00:00",
                }
            ]

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    result = await get_sales_quality_training_advice()

    assert result["available"] is True
    assert result["advice"][0]["manager_name"] == "Low Scorer"


@pytest.mark.asyncio
async def test_training_advice_route_scopes_rows_for_seller_principal(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice
    from src.api.rbac import Principal, Role

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return [
                {"manager_id": 1, "manager_name": "Manager One", "advice_text": "A", "generated_at": "t"},
                {"manager_id": 2, "manager_name": "Manager Two", "advice_text": "B", "generated_at": "t"},
            ]

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    seller = Principal(subject="1", role=Role.SELLER, auth_type="test")

    result = await get_sales_quality_training_advice(principal=seller)

    assert result["available"] is True
    assert len(result["advice"]) == 1
    assert result["advice"][0]["manager_id"] == 1
