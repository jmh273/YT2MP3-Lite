@echo off
title YT2MP3-Lite Frontend
cd /d %~dp0frontend
echo ========================================
echo  YT2MP3-Lite Frontend (port 5173)
echo ========================================
echo.
call npm run dev -- --open
echo.
echo Frontend stopped. Press any key to close.
pause >nul
