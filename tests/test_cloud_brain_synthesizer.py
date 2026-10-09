import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.schedulers.cloud_brain_synthesizer import (
    _fetch_recent_data,
    _generate_insights,
    run_brain_synthesizer_cycle,
)
from src.services.utils.free_ai_router import ProviderResult

@pytest.mark.asyncio
async def test_generate_insights_empty():
    assert await _generate_insights("") is None
    assert await _generate_insights(None) is None

@pytest.mark.asyncio
async def test_generate_insights_success():
    fake_result = ProviderResult(
        text="### 1. 🔄 Context Switching\n- Task A done\n### 2. 💡 Content Machine\n- Idea 1",
        provider="groq",
        model="compound"
    )
    with patch("src.schedulers.cloud_brain_synthesizer.FreeAIProviderRouter") as mock_router_cls:
        mock_router = MagicMock()
        mock_router.generate_text = AsyncMock(return_value=fake_result)
        mock_router_cls.return_value = mock_router

        result = await _generate_insights("Task: 1 - Design logo")
        assert result is not None
        assert "Context Switching" in result

@pytest.mark.asyncio
async def test_generate_insights_failure_fails_closed():
    with patch("src.schedulers.cloud_brain_synthesizer.FreeAIProviderRouter") as mock_router_cls:
        mock_router = MagicMock()
        mock_router.generate_text = AsyncMock(side_effect=RuntimeError("All providers failed"))
        mock_router_cls.return_value = mock_router

        result = await _generate_insights("Task: 1 - Design logo")
        # Fail-closed: returns None instead of an error message
        assert result is None

@pytest.mark.asyncio
async def test_run_cycle_skips_when_no_data():
    bot = AsyncMock()
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="")):
        await run_brain_synthesizer_cycle(bot, 12345)
        bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_skips_when_no_insights():
    bot = AsyncMock()
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=None)):
            await run_brain_synthesizer_cycle(bot, 12345)
            bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_skips_when_mostly_no_data():
    bot = AsyncMock()
    sparse_text = "### 1. Ma'lumot yo'q.\n### 2. Ma'lumot yo'q.\n### 3. Ma'lumot yo'q.\n### 4. Ma'lumot yo'q."
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=sparse_text)):
            await run_brain_synthesizer_cycle(bot, 12345)
            bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_sends_on_valid_insights():
    bot = AsyncMock()
    valid_text = "### 1. 🔄 Context Switching\n- Next step\n### 2. 💡 Content Machine\n- Idea"
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=valid_text)):
            with patch("src.schedulers.cloud_brain_synthesizer.push_vault_to_remote", AsyncMock()):
                await run_brain_synthesizer_cycle(bot, 12345)
                bot.send_message.assert_called_once()
                args, kwargs = bot.send_message.call_args
                assert args[0] == 12345
                assert "Second Brain Evolution Digest" in args[1]
                assert "Context Switching" in args[1]


@pytest.fixture(autouse=True)
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "brain_digest_state.txt"
    monkeypatch.setattr("src.schedulers.cloud_brain_synthesizer.STATE_FILE", path)
    return path


VALID_TEXT = "### 1. 🔄 Kontekst\n- Keyingi qadam\n### 2. 💡 G'oyalar\n- G'oya"


@pytest.mark.asyncio
async def test_run_cycle_skips_unchanged_tasks(state_file):
    bot = AsyncMock()
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: Logo - X")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=VALID_TEXT)) as gen:
            with patch("src.schedulers.cloud_brain_synthesizer.push_vault_to_remote", AsyncMock()):
                await run_brain_synthesizer_cycle(bot, 1)
                await run_brain_synthesizer_cycle(bot, 1)
    assert bot.send_message.call_count == 1
    assert gen.call_count == 1
    assert state_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_cycle_sends_again_when_tasks_change(state_file):
    bot = AsyncMock()
    fetch = AsyncMock(side_effect=["Task: Logo - X", "Task: Brandbook - Y"])
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", fetch):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=VALID_TEXT)):
            with patch("src.schedulers.cloud_brain_synthesizer.push_vault_to_remote", AsyncMock()):
                await run_brain_synthesizer_cycle(bot, 1)
                await run_brain_synthesizer_cycle(bot, 1)
    assert bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_run_cycle_disabled_by_env(state_file, monkeypatch):
    monkeypatch.setenv("ENABLE_BRAIN_DIGEST", "0")
    bot = AsyncMock()
    fetch = AsyncMock(return_value="Task: Logo - X")
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", fetch):
        await run_brain_synthesizer_cycle(bot, 1)
    fetch.assert_not_called()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_filters_demo_tasks():
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=[
        ("Buyurtmachi A bilan uchrashuv", ""),
        ("Dastur xatolarini tuzatish", None),
        ("Sotuvchilar uchun qo'llanma yozish", ""),
        ("Uchrashuv Buyurtmachi A $1500", "Yangi loyiha"),
        ("Dastur  Xatolarini tuzatish", "Login sahifasidagi xato"),
        ("Sotuvchilar uchun qo\u2018llanma", "Yangi xodimlar uchun"),
        ("Nike brandbook", "Deadline juma"),
        ("Buyurtmachi Ali bilan uchrashuv", None),
    ])
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cursor)
    db = MagicMock()
    db.get_connection = AsyncMock(return_value=conn)
    with patch("src.schedulers.cloud_brain_synthesizer.get_db", return_value=db):
        data = await _fetch_recent_data()
    assert data == "Task: Nike brandbook - Deadline juma\nTask: Buyurtmachi Ali bilan uchrashuv - None"
