@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo ========================================
echo  BeamSkin Studio - Prepare for Release
echo ========================================
echo.

REM ── 1. Clear Python cache ────────────────────────────────────────────────────

echo [1/7] Removing Python cache folders...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" ( rd /s /q "%%d" 2>nul )
)

echo [2/7] Removing compiled Python files (.pyc)...
for /r . %%f in (*.pyc) do (
    if exist "%%f" ( del /f /q "%%f" 2>nul )
)

echo [3/7] Removing optimized Python files (.pyo)...
for /r . %%f in (*.pyo) do (
    if exist "%%f" ( del /f /q "%%f" 2>nul )
)

echo [4/7] Removing temporary files...
if exist "temp"  ( rd /s /q "temp"  2>nul )
if exist "cache" ( rd /s /q "cache" 2>nul )
for %%f in (*.tmp) do ( del /f /q "%%f" 2>nul )
if exist "Thumbs.db"   ( del /f /q /a "Thumbs.db" 2>nul )
if exist "desktop.ini" ( attrib -h -s "desktop.ini" 2>nul & del /f /q "desktop.ini" 2>nul )

echo [5/7] Removing log files...
for %%f in (*.log) do ( del /f /q "%%f" 2>nul )

REM ── 2. Reset first launch ────────────────────────────────────────────────────

set "SETTINGS_FILE=data\app_settings.json"

echo [6/7] Resetting first launch settings...
if not exist "%SETTINGS_FILE%" (
    echo   WARNING: %SETTINGS_FILE% not found - skipping reset.
) else (
    powershell -Command "& {$json = Get-Content '%SETTINGS_FILE%' -Raw | ConvertFrom-Json; $json.first_launch = $true; $json.setup_complete = $false; $json.beamng_install = ''; $json.mods_folder = ''; $json | ConvertTo-Json -Depth 10 | Set-Content '%SETTINGS_FILE%'}"
    if errorlevel 1 (
        echo   ERROR: Failed to reset settings.
    )
)

echo [7/7] Clearing seen changelogs...
if exist "data\seen_changelogs.json" ( del /f /q "data\seen_changelogs.json" 2>nul )

echo.
echo ========================================
echo  Done! Ready for release.
echo ========================================
echo.
pause
