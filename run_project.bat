@echo off
SETLOCAL
TITLE TrendSense - Fullstack Starter

echo ===================================================
echo 🚀 TrendSense: Starting Backend ^& Frontend
echo ===================================================

:: Navigate to project root (just in case)
cd /d "%~dp0"

:: Step 1: Start Backend in a new window
echo [*] Launching FastAPI Backend on port 8000...
start cmd /k "TITLE TrendSense-Backend && echo STARTING BACKEND... && venv\Scripts\activate && python -m uvicorn backend.main:app --reload --port 8000"

:: Step 2: Start Frontend in a new window
echo [*] Launching Next.js Frontend on port 3000...
start cmd /k "TITLE TrendSense-Frontend && echo STARTING FRONTEND... && cd frontend && npm run dev"

echo.
echo [OK] Both servers are starting in separate windows.
echo    - Backend:  http://127.0.0.1:8000
echo    - Frontend: http://localhost:3000
echo.
echo Press any key to close this launcher (servers will keep running).
pause > nul
