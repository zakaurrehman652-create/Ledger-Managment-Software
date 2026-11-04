@echo off
title Tri Agro Farms - Ledger Management System
cls
echo ====================================================================
echo        TRI AGRO FARMS - LEDGER & MANAGEMENT SYSTEM (PKR)
echo ====================================================================
echo.
echo   Localhost Access Links:
echo     [1] Login / Portal: http://localhost:8000
echo     [2] Dashboard:      http://localhost:8000/dashboard.html
echo     [3] API Swagger:    http://localhost:8000/docs
echo.
echo   Starting server and opening system in your default browser...
echo   (Keep this window open. Press Ctrl+C to stop the server)
echo ====================================================================
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"
python main.py
pause
