@echo off
setlocal
cd /d %~dp0

REM Starts the application modules, each in its own window.
REM
REM   run_all.bat                      start models, backend and frontend
REM   run_all.bat backend frontend     start only the modules named
REM   run_all.bat --no-models          start everything except models
REM   run_all.bat --no-frontend backend
REM
REM Module names: models, backend, frontend. Naming a module selects only the
REM named modules; --no-<module> removes one from the selection either way.

set "START_MODELS=0"
set "START_BACKEND=0"
set "START_FRONTEND=0"
set "ANY_PICK=0"
set "NO_MODELS=0"
set "NO_BACKEND=0"
set "NO_FRONTEND=0"

for %%A in (%*) do (
    if /i "%%A"=="models" (set "START_MODELS=1" & set "ANY_PICK=1")
    if /i "%%A"=="backend" (set "START_BACKEND=1" & set "ANY_PICK=1")
    if /i "%%A"=="frontend" (set "START_FRONTEND=1" & set "ANY_PICK=1")
    if /i "%%A"=="--no-models" set "NO_MODELS=1"
    if /i "%%A"=="--no-backend" set "NO_BACKEND=1"
    if /i "%%A"=="--no-frontend" set "NO_FRONTEND=1"
)

if "%ANY_PICK%"=="0" (set "START_MODELS=1" & set "START_BACKEND=1" & set "START_FRONTEND=1")
if "%NO_MODELS%"=="1" set "START_MODELS=0"
if "%NO_BACKEND%"=="1" set "START_BACKEND=0"
if "%NO_FRONTEND%"=="1" set "START_FRONTEND=0"

REM Models first: it takes minutes to load weights, so it should start early.
REM The backend does not wait for it; the backend restarts in seconds.
if "%START_MODELS%"=="1" echo Starting models service...
if "%START_MODELS%"=="1" start "Models" cmd /k call "%~dp0models\run_models.bat"

if "%START_BACKEND%"=="1" echo Starting backend...
if "%START_BACKEND%"=="1" start "Backend" cmd /k call "%~dp0backend\run_backend.bat"

if "%START_FRONTEND%"=="1" echo Starting frontend...
if "%START_FRONTEND%"=="1" start "Frontend" cmd /k call "%~dp0frontend\run_frontend.bat"

if "%START_MODELS%%START_BACKEND%%START_FRONTEND%"=="000" echo Nothing selected to start.

echo.
echo   Models:   http://localhost:8001
echo   API:      http://localhost:8000/health
echo   App:      http://localhost:3000
echo.
pause
exit /b 0
