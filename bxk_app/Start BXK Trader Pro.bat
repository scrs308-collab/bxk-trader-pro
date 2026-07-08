@echo off
title BXK Trader Pro

cd /d "%~dp0"

echo.
echo ============================
echo    Starting BXK Trader Pro
echo ============================
echo.

call .venv\Scripts\activate.bat

git checkout v4
git pull

start "" http://127.0.0.1:8000

python -m uvicorn bxk_app.main:app --reload