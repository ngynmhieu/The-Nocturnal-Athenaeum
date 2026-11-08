@echo off
setlocal
cd /d %~dp0
echo Installing dependencies...
call npm install
echo Starting dev server...
call npm run dev
pause
