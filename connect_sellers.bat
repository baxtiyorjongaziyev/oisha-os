@echo off
chcp 65001 >nul
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\connect_corporate_seller.py"
pause
