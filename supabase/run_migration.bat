@echo off
setlocal
cd /d %~dp0..

REM Schema -> migration -> apply, in one step.
REM Detects changed schema/<module>/*.sql fragments, generates per-table
REM migrations, shows the diff, and applies them to your LOCAL Supabase
REM database (supabase migration up --local) after you confirm. Requires
REM the local stack to be running (supabase start / deploy.bat supabase).
REM
REM Pass-through flags (see supabase/docs/supabase_guidelines.md):
REM   run_migration.bat             detect -> generate -> review -> prompt to apply
REM   run_migration.bat --status    only report what changed; generate nothing
REM   run_migration.bat --no-apply  generate + review, never apply
REM   run_migration.bat --yes       skip the prompt; apply if there's anything to apply

where python >nul 2>nul
if errorlevel 1 (
    echo error: python is not on PATH. Install Python or open a shell where it is available.
    exit /b 1
)

python supabase\scripts\sync_schema.py %*
exit /b %errorlevel%
