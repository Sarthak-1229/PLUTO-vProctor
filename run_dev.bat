@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ======================================================================
echo Starting PLUTO vProctor Development Servers
echo ======================================================================

echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "PLUTO Backend (FastAPI)" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching React Vite Frontend on http://localhost:5173 ...
start "PLUTO Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo ======================================================================
echo Both servers have been launched in separate terminal windows.
echo - Backend API:  http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
echo - Frontend Web: http://localhost:5173
echo Opening http://localhost:5173 in your default browser...
echo ======================================================================

timeout /t 3 /nobreak >nul
start http://localhost:5173
