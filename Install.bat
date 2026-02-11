@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo BeamSkin Studio - Dependency Installer & Auto-Updater
echo ============================================================
echo.

echo [1/7] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python is not installed!
    echo Downloading and installing Python 3.11...
    if not exist "%TEMP%\BeamSkinStudio" mkdir "%TEMP%\BeamSkinStudio"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\BeamSkinStudio\python_installer.exe'}"
    start /wait %TEMP%\BeamSkinStudio\python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
    start "" "%~f0"
    exit
)

echo [2/7] Detecting Python installations...
set "PYTHON_LIST=%TEMP%\python_installations.txt"
where python > "%PYTHON_LIST%" 2>nul
set INSTALL_COUNT=0
for /f "delims=" %%p in ('type "%PYTHON_LIST%"') do (
    set /a INSTALL_COUNT+=1
)
echo Total: !INSTALL_COUNT! Python installations detected.

echo [3/7] Auto-updating pip...
python -m pip install --upgrade pip --quiet 

echo [4/7] Auto-updating dependencies...
echo Checking for updates: CustomTkinter, Pillow, Requests, pywin32...
python -m pip install --upgrade customtkinter Pillow requests pywin32 --quiet

echo [6/7] Verifying versions...
python -c "import customtkinter; import PIL; import requests; print('[OK] All dependencies are up to date')"

echo [7/7] Starting BeamSkin Studio...
timeout /t 2 /nobreak >nul
if exist "BeamSkin Studio.bat" (
    start "" "BeamSkin Studio.bat" [cite: 37]
    exit
) else (
    echo [ERROR] Main application file not found.
    pause
    exit
)