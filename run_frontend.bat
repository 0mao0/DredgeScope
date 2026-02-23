@echo off
setlocal
cd /d "%~dp0frontend"
call pnpm install
call pnpm run dev
pause
