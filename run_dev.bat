@echo off
echo Starting DredgeScope Development Environment...

:: Start Backend Dashboard
start "DredgeScope Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn reporting.dashboard_server:app --reload --host 127.0.0.1 --port 8000"

:: Start Scheduler
start "DredgeScope Scheduler" cmd /k "cd /d %~dp0backend && python -m scheduler"

:: Start Frontend
start "DredgeScope Frontend" cmd /k "cd /d %~dp0frontend && pnpm run dev"

echo All services started in separate windows.
