@echo off
chcp 65001 > nul
echo ========================================================
echo   OISHA-OS: O'Z TELEGRAM SUHBATLARINGIZNI AI BILAN TAHLIL QILISH
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe scripts\test_analyze_my_chats.py
) else (
    python scripts\test_analyze_my_chats.py
)

pause
