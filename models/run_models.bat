@echo off
setlocal
cd /d %~dp0..

REM Create the venv if missing
if not exist "models\.venv" (
    echo Creating virtual environment in models folder...
    cd models
    python -m venv .venv
    cd ..
)

REM Activate it
call models\.venv\Scripts\activate.bat

REM Ensure dependencies are installed (self-heals an empty or partial venv)
python -c "import uvicorn" 2>NUL
if errorlevel 1 (
    echo Installing requirements...
    pip install -r models\requirements.txt
)

REM Run the models service
python -m models.run_models
