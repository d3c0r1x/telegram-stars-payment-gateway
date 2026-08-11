@echo off
rem Launch script for the Telegram Stars Payment Gateway (Project 4).
rem Reads TG_TOKEN from the root .env, sets WB_BOT_TOKEN, runs the bot.
cd /d "%~dp0"

for /f "usebackq tokens=1,* delims==" %%a in ("..\.env") do (
    if "%%a"=="TG_TOKEN" set "WB_BOT_TOKEN=%%b"
)
if not defined WB_BOT_TOKEN (
    echo [ERROR] TG_TOKEN not found in ..\.env
    pause
    exit /b 1
)

rem 1 = Telegram Stars (empty provider_token, currency XTR) | 0 = YooKassa test mode
set "STAR_PAYMENTS=1"
set "PYTHONIOENCODING=utf-8"

rem --- YOOKASSA TEST MODE: ---
rem 1) set "STAR_PAYMENTS=0"
rem 2) set "YOOKASSA_PROVIDER_TOKEN=<test token from @BotFather, Payments menu>"
rem 3) restart this script.

..\.venv\Scripts\python.exe -u bot.py
