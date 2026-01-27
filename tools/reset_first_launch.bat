@echo off
REM Reset First Launch Settings for BeamSkin Studio
REM This script resets the first_launch and setup_complete flags

echo ========================================
echo BeamSkin Studio - Reset First Launch
echo ========================================
echo.

REM Change to parent directory (main program folder)
cd /d "%~dp0\.."

set "SETTINGS_FILE=data\app_settings.json"

REM Check if settings file exists
if not exist "%SETTINGS_FILE%" (
    echo ERROR: Settings file not found at %SETTINGS_FILE%
    echo Please run this script from the BeamSkin Studio root folder.
    echo.
    pause
    exit /b 1
)

echo Current settings file: %SETTINGS_FILE%
echo.
echo Creating backup...

REM Create backup with timestamp
set "TIMESTAMP=%date:~-4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
copy "%SETTINGS_FILE%" "data\app_settings_backup_%TIMESTAMP%.json" >nul

if errorlevel 1 (
    echo ERROR: Failed to create backup!
    echo.
    pause
    exit /b 1
)

echo Backup created: app_settings_backup_%TIMESTAMP%.json
echo.
echo Resetting first launch settings...

REM Use PowerShell to modify the JSON file
powershell -Command "& {$json = Get-Content '%SETTINGS_FILE%' -Raw | ConvertFrom-Json; $json.first_launch = $true; $json.setup_complete = $false; $json.beamng_install = ''; $json.mods_folder = ''; $json | ConvertTo-Json -Depth 10 | Set-Content '%SETTINGS_FILE%'}"

if errorlevel 1 (
    echo ERROR: Failed to modify settings!
    echo Restoring backup...
    copy "data\app_settings_backup_%TIMESTAMP%.json" "%SETTINGS_FILE%" >nul
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo The following changes were made:
echo   - first_launch: changed to TRUE
echo   - setup_complete: changed to FALSE
echo   - beamng_install: cleared (empty)
echo   - mods_folder: cleared (empty)
echo.
echo Next time you launch BeamSkin Studio, you will see:
echo   1. The setup wizard
echo   2. The WIP warning dialog
echo.
echo Your backup is saved as: app_settings_backup_%TIMESTAMP%.json
echo.
pause
