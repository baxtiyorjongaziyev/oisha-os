@echo off
chcp 65001 > nul
echo ========================================================
echo   OISHA-OS: TELEGRAM 3 YILLIK ARXIVINI AVTONOM TAHLIL QILISH
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe scripts\crawl_telegram_history.py
) else (
    python scripts\crawl_telegram_history.py
)

pause
