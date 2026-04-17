@echo off
cd /d "C:\Users\baxti\playground\oisha-os"

chcp 65001 >nul
set PYTHONIOENCODING=utf-8

if not exist .venv_oi\Scripts\python.exe (
    echo [INFO] Open Interpreter uchun .venv_oi Python 3.12 yaratilmoqda...
    py -3.12 -m venv .venv_oi
    if errorlevel 1 (
        echo [ERROR] Python 3.12 topilmadi yoki venv yaratib bo'lmadi.
        exit /b 1
    )
)

call .venv_oi\Scripts\activate.bat

python -m pip show open-interpreter >nul 2>nul
if errorlevel 1 (
    echo [INFO] open-interpreter o'rnatilmoqda...
    python -m pip install -U open-interpreter
)

interpreter --auto_run --safe_mode off
