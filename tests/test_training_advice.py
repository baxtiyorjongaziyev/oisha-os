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
