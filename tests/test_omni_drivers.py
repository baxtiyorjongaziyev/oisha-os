"""
Unit tests for Oisha WebDriver, OSDriver, and MobileProxy.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.agents.web_driver import OishaWebDriver
from src.agents.os_driver import OishaOSDriver
from src.agents.mobile_proxy import OishaMobileProxy, OishaTelegramProxy


try:
    import instagrapi
    HAS_INSTAGRAPI = True
except ImportError:
    HAS_INSTAGRAPI = False


def test_os_driver_initialization():
    """OS Driver to'g'ri yaratilishini tekshirish."""
    driver = OishaOSDriver()
    assert driver is not None
    # PyAutoGUI global sozlamalarini tekshirish
    import pyautogui
    assert pyautogui.FAILSAFE is True


@pytest.mark.skipif(not HAS_INSTAGRAPI, reason="instagrapi package is not installed")
def test_mobile_proxy_initialization():
    """Mobile Proxy to'g'ri yaratilishini tekshirish."""
    # instagrapi load bo'lishini tekshirish (username va password bo'lmasa xatolik berishi kerak login() da)
    proxy = OishaMobileProxy(username="test_user", password="test_password")
    assert proxy.username == "test_user"
    assert proxy.password == "test_password"


def test_telegram_proxy_initialization():
    """Telegram Proxy to'g'ri yaratilishini tekshirish."""
    mock_client = MagicMock()
    proxy = OishaTelegramProxy()
    proxy.set_client(mock_client)
    assert proxy.client == mock_client
    assert proxy._initialized is True


@pytest.mark.asyncio
async def test_web_driver_initialization(monkeypatch):
    """WebDriver initialization va mock start/stop tekshirish."""
    driver = OishaWebDriver()
    assert driver.page is None
    
    # playwright'ni mock qilish
    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    
    # context manager and start method
    mock_context_manager = MagicMock()
    mock_context_manager.start = AsyncMock(return_value=mock_playwright)
    mock_async_playwright = MagicMock(return_value=mock_context_manager)
    
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    
    monkeypatch.setattr("src.agents.web_driver.async_playwright", mock_async_playwright)
    
    # start() ni chaqirish
    await driver.start(headless=True)
    assert driver.page == mock_page
    
    # stop() ni chaqirish
    await driver.stop()
    assert driver.page is None
