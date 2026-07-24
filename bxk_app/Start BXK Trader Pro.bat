@echo off
cd /d C:\Projects\bxk-trader-pro
start "" http://127.0.0.1:8000
python -m uvicorn bxk_app.main:app --reload
pause
