@echo off
setlocal
cd /d "%~dp0backend"
py -3 -m uvicorn reporting.dashboard_server:app --reload --host 127.0.0.1 --port 8001
pause
