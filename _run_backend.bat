@echo off
title YT2MP3-Lite Backend
cd /d %~dp0backend
echo ========================================
echo  YT2MP3-Lite Backend (port 8010)
echo ========================================
echo.
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
echo.
echo Backend stopped. Press any key to close.
pause >nul
