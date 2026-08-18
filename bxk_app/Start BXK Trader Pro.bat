@echo off
title BXK Trader Pro
cd /d C:\Projects\bxk-trader-pro

echo.
echo ========================================
echo        BXK Trader Pro
echo ========================================
echo.
echo Starting secure BXK server...
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/'"

"C:\Projects\bxk-trader-pro\.venv\Scripts\python.exe" -m uvicorn bxk_app.main:app --host 127.0.0.1 --port 8000

echo.
echo BXK Trader Pro has stopped.
pause
