@echo off
if "%1"=="backend" goto backend
if "%1"=="frontend" goto frontend

SETLOCAL
TITLE TrendSense - Fullstack Starter

:: Main launcher code
cd /d "%~dp0"
set PYTHONPATH=%cd%

echo ===================================================
echo  TrendSense: Starting Backend and Frontend
echo ===================================================

echo [*] Launching FastAPI Backend on port 8080...
start "TrendSense-Backend" "%~dpnx0" backend

:: Wait for backend
echo [*] Waiting 10s for backend boot...
ping 127.0.0.1 -n 11 > nul

echo [*] Launching Next.js Frontend on port 3000...
start "TrendSense-Frontend" "%~dpnx0" frontend

echo.
echo [OK] Both servers are starting.
echo    - Backend: http://127.0.0.1:8080/docs
echo    - Frontend: http://localhost:3000
echo.
echo Press any key to close this launcher.
pause > nul
exit /b

:backend
:: Backend logic
title TrendSense-Backend
cd /d "%~dp0"
set PYTHONPATH=%cd%
call venv\Scripts\activate.bat
echo STARTING BACKEND...
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Backend failed to start.
    pause
)
cmd /k
exit /b

:frontend
:: Frontend logic
title TrendSense-Frontend
cd /d "%~dp0\frontend"
echo STARTING FRONTEND...
npm run dev
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Frontend failed to start.
    pause
)
cmd /k
exit /b
