import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.auto_execution import AutonomousExecutor
from src.services.utils.voice_processor import VoiceProcessor


@pytest.mark.asyncio
async def test_auto_executor_generate_contract_pdf():
    # Arrange
    mock_db = MagicMock()
    mock_airtable = MagicMock()

    executor = AutonomousExecutor(db=mock_db, airtable=mock_airtable)

    # Act
    pdf_path = await executor.generate_contract_pdf("Akmal", "Acme Corp", 50000000)

    # Assert
    import os
    assert os.path.exists(pdf_path)
    # Cleanup
    os.remove(pdf_path)


@pytest.mark.asyncio
async def test_auto_executor_send_invoice_draft():
    # Arrange
    mock_db = MagicMock()
    mock_airtable = MagicMock()

    executor = AutonomousExecutor(db=mock_db, airtable=mock_airtable)
    
    # Mock WebDriverWrapper
    executor.web_driver.start = AsyncMock()
    executor.web_driver.stop = AsyncMock()

    # Act
    success = await executor.send_invoice_draft(12345, 12000000.0)

    # Assert
    assert success is True
    executor.web_driver.start.assert_called_once()
    executor.web_driver.stop.assert_called_once()


@pytest.mark.asyncio
async def test_voice_processor_convert_voice_to_task_success():
    # Arrange
    processor = VoiceProcessor(api_key="mock_key")
    
    # Mock transcribe and generate_content_with_fallback
    processor.transcribe = AsyncMock(return_value="Diyorga naming vazifasini 2026-06-30 gacha topshir.")
    
    mock_response = MagicMock()
    mock_response.text = '{"title": "Naming Task", "description": "Diyorga naming vazifasini topshirish", "assigned_to": "Diyor", "deadline": "2026-06-30"}'
    
    # Act
    with patch("src.services.utils.voice_processor.generate_content_with_fallback", return_value=(mock_response, None)):
        task_data = await processor.convert_voice_to_task("fake_voice_path.ogg")

        # Assert
        assert task_data["title"] == "Naming Task"
        assert task_data["assigned_to"] == "Diyor"
        assert task_data["deadline"] == "2026-06-30"
