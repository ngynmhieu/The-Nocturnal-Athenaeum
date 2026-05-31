@echo off
setlocal
cd /d %~dp0
call .venv\Scripts\activate.bat
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
