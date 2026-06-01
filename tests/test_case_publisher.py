import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.case_publisher import CasePublisher


def _mock_genai_client():
    client = MagicMock()
    client.aio = None
    return client


@pytest.mark.asyncio
async def test_is_portfolio_case_classification_success():
    client_mock = MagicMock()
    publisher = CasePublisher(client=client_mock)

    with patch(
        "src.services.utils.gemini_fallback.generate_content_with_fallback",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_response = MagicMock()
        mock_response.text = "YES"
        mock_call.return_value = (mock_response, "gemini-test")
        
        is_case = await publisher.is_portfolio_case("Quyidagi yangi brending keysimiz va dizayn konsepsiyamiz juda ajoyib va chiroyli chiqdi.")
        assert is_case is True


@pytest.mark.asyncio
async def test_is_portfolio_case_classification_failure():
    client_mock = MagicMock()
    publisher = CasePublisher(client=client_mock)

    with patch(
        "src.services.utils.gemini_fallback.generate_content_with_fallback",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_response = MagicMock()
        mock_response.text = "NO"
        mock_call.return_value = (mock_response, "gemini-test")
        
        is_case = await publisher.is_portfolio_case("Bugun havo juda ham ajoyib va quyoshli bo'lib, hammaga xayrli kun tilab qolaman do'stlar.")
        assert is_case is False


@pytest.mark.asyncio
async def test_extract_case_details_success():
    client_mock = MagicMock()
    publisher = CasePublisher(client=client_mock, genai_client=_mock_genai_client())

    mock_response = MagicMock()
    mock_response.text = (
        '{"title": "Oqtepa Lavash Branding", "client": "Oqtepa", "short_description": "New Identity", '
        '"challenge": "Rebrand", "solution": "New Logo", "results": "Increased sales", "tags": ["branding"]}'
    )

    # Patch the generate_content call on genai_client.models
    with patch.object(
        publisher.genai_client.models, "generate_content", return_value=mock_response
    ):
        details = await publisher.extract_case_details("Oqtepa lavash loyihamiz...")
        assert details["title"] == "Oqtepa Lavash Branding"
        assert details["client"] == "Oqtepa"
        assert details["tags"] == ["branding"]


@pytest.mark.asyncio
async def test_publish_case_dispatch_webhook_success():
    client_mock = MagicMock()
    publisher = CasePublisher(client=client_mock)

    case_data = {
        "title": "Test Case",
        "client": "Test Client",
        "tags": ["design"]
    }

    # Mock httpx AsyncClient post
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch.dict("os.environ", {"CMS_WEBHOOK_URL": "https://test-cms.com/webhook"}):
         
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "OK"

        success = await publisher.publish_case(case_data, [])
        assert success is True
        mock_post.assert_called_once()
