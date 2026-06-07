@echo off
setlocal
cd /d %~dp0

REM Check if venv exists in backend folder
if not exist "backend\.venv" (
    echo Creating virtual environment in backend folder...
    cd backend
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing requirements...
    pip install -r requirements.txt
    cd ..
) else (
    cd backend
    call .venv\Scripts\activate.bat
    cd ..
)

REM Run the backend
python -m backend.run_backend
