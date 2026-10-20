@echo off
echo ======================================================================
echo Starting PLUTO vProctor Development Servers
echo ======================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "PLUTO Backend (FastAPI)" cmd /k "cd /d "%SCRIPT_DIR%" && backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching React Vite Frontend on http://localhost:5173 ...
start "PLUTO Frontend (Vite)" cmd /k "cd /d "%SCRIPT_DIR%frontend" && npm run dev"

echo.
echo Both servers started in background windows.
echo - Backend API:  http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
echo - Frontend Web: http://localhost:5173
echo ======================================================================
