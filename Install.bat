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

echo [4/7] Checking and installing dependencies...

echo Checking Pillow (image processing)...
python -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Pillow not found - installing...
    python -m pip install Pillow --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Pillow!
        pause
        exit /b 1
    )
    echo   [OK] Pillow installed.
) else (
    echo   [OK] Pillow already installed - upgrading if needed...
    python -m pip install --upgrade Pillow --quiet
)

echo Checking other dependencies: CustomTkinter, Requests, pywin32, emoji-country-flag, deep-translator...
python -m pip install --upgrade customtkinter requests pywin32 emoji-country-flag deep-translator --quiet

echo [6/7] Verifying versions...
python -c "import customtkinter; import PIL; import requests; import flag; import deep_translator; print('[OK] All dependencies are up to date')"

echo [7/7] Starting BeamSkin Studio...
timeout /t 2 /nobreak >nul
if exist "BeamSkin Studio.bat" (
    start "" "BeamSkin Studio.bat"
    exit
) else (
    echo.
    echo ============================================================
    echo  [ERROR] Could not find "BeamSkin Studio.bat"
    echo ============================================================
    echo.
    echo  This usually means one of the following:
    echo.
    echo  1. The file is missing from this folder.
    echo     - Try launching "BeamSkin Studio.bat" manually if it
    echo       exists somewhere else in the BeamSkin Studio folder.
    echo.
    echo  2. The program files are incomplete or weren't fully downloaded.
    echo     - Try downloading BeamSkin Studio again and re-running
    echo       this installer from the newly extracted folder.
    echo.
    echo  3. If the issue keeps happening after re-downloading, you can
    echo     contact the developer for help:
    echo.
    echo       Email: burztworkshop@gmail.com
    echo.
    echo ============================================================
    echo.
    pause
    exit
)