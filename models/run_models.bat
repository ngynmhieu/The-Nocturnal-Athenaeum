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

REM Ensure dependencies are installed (self-heals an empty, partial or pre-llama.cpp
REM venv). find_spec, not import: llama_cpp only imports after cuda_bootstrap runs.
python -c "import importlib.util as u, sys; sys.exit(not all(u.find_spec(m) for m in ['uvicorn', 'llama_cpp', 'jinja2']))" 2>NUL
if errorlevel 1 (
    echo Installing requirements...
    pip install -r models\requirements.txt
)

REM Run the models service
python -m models.run_models
