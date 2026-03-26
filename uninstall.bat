@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo BeamSkin Studio - Dependency Uninstaller (Dev Tool)
echo ============================================================
echo.
echo This will uninstall all packages installed by install.bat:
echo   - Pillow, customtkinter, requests, pywin32, flagpy, deep-translator
echo.
echo NOTE: Python itself will NOT be uninstalled automatically.
echo       See end of script for instructions if needed.
echo.
set /p CONFIRM="Are you sure you want to continue? (y/n): "
if /i "!CONFIRM!" neq "y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo [1/3] Uninstalling pip packages...
python -m pip uninstall -y Pillow customtkinter requests pywin32 flagpy deep-translator pywin32-ctypes

if %errorlevel% neq 0 (
    echo [WARNING] Some packages may not have been fully removed.
) else (
    echo [OK] Packages uninstalled.
)

echo.
echo [2/3] Cleaning up temp files from installer...
if exist "%TEMP%\BeamSkinStudio" (
    rmdir /s /q "%TEMP%\BeamSkinStudio"
    echo [OK] Temp folder removed.
) else (
    echo [SKIP] No temp folder found.
)

if exist "%TEMP%\python_installations.txt" (
    del /f /q "%TEMP%\python_installations.txt"
    echo [OK] Temp file removed.
)

echo.
echo [3/3] Verifying removal...
python -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] Pillow removed.) else (echo   [WARN] Pillow still present.)

python -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] customtkinter removed.) else (echo   [WARN] customtkinter still present.)

python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] requests removed.) else (echo   [WARN] requests still present.)

python -c "import win32api" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] pywin32 removed.) else (echo   [WARN] pywin32 still present.)

python -c "import flag" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] flagpy removed.) else (echo   [WARN] flagpy still present.)

python -c "import deep_translator" >nul 2>&1
if %errorlevel% neq 0 (echo   [OK] deep-translator removed.) else (echo   [WARN] deep-translator still present.)

echo.
echo ============================================================
echo Done! You can now re-run install.bat to test a clean install.
echo.
echo To also uninstall Python (if install.bat installed it):
echo   1. Open Settings ^> Apps ^> Installed Apps
echo   2. Search for "Python 3.11" and uninstall it
echo   OR run: %TEMP%\BeamSkinStudio\python_installer.exe /uninstall
echo      (only works if the temp file still exists)
echo ============================================================
echo.
pause
