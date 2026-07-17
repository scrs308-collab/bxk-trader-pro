@echo off
title BXK Trader Pro

cd /d "%~dp0"

call .venv\Scripts\activate.bat

start "" http://127.0.0.1:8000

python -m uvicorn bxk_app.main:app --reload
