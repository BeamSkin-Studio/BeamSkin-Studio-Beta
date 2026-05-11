@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo BeamSkin Studio - Dependency Installer ^& Auto-Updater
echo ============================================================
echo.

:: -----------------------------------------------------------
:: Step 1: Locate Python — try multiple methods
:: -----------------------------------------------------------
echo [1/7] Checking Python installation...
set "PYTHON_CMD="

:: 1a. Try 'python' directly (classic PATH entry)
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

:: 1b. Try 'py' (Windows Python Launcher — common with 3.12 installs)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

:: 1c. Try 'py -3' (explicit Python 3 via launcher)
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :python_found
)

:: 1d. Try 'python3'
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :python_found
)

:: 1e. Probe common install paths for 3.12, 3.11, 3.10, 3.9, 3.8
for %%V in (312 311 310 39 38) do (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        "%ProgramFiles%\Python%%V\python.exe"
        "%ProgramFiles(x86)%\Python%%V\python.exe"
    ) do (
        if exist %%P (
            %%P --version >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_CMD=%%P"
                goto :python_found
            )
        )
    )
)

:: 1f. Check Windows Store location (verify it's not a dead stub)
for %%P in (
    "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
    "%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe"
) do (
    if exist %%P (
        %%P --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=%%P"
            goto :python_found
        )
    )
)

:: Nothing found — offer to download and install Python automatically
echo.
echo [WARNING] Python was not found on this system.
echo.
set /p "DO_INSTALL=Download and install Python 3.11 automatically? [Y/N]: "
if /i not "%DO_INSTALL%"=="Y" (
    echo Cancelled. Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during setup.
    pause
    exit /b 1
)

echo Downloading Python 3.11.9...
if not exist "%TEMP%\BeamSkinStudio" mkdir "%TEMP%\BeamSkinStudio"
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\BeamSkinStudio\python_installer.exe'}"
if %errorlevel% neq 0 (
    echo [ERROR] Download failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo Installing Python (this may take a minute)...
set "PY_INSTALL_DIR=%ProgramFiles%\Python311"
start /wait "%TEMP%\BeamSkinStudio\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 TargetDir="%PY_INSTALL_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] Python installer returned an error. Try installing manually from https://python.org
    pause
    exit /b 1
)

:: Point directly at the known install path — do NOT restart the script.
:: Restarting won't work because the new PATH only takes effect in a fresh
:: login session; the re-launched cmd would loop back here and install again.
set "PYTHON_CMD=%PY_INSTALL_DIR%\python.exe"
if not exist "%PYTHON_CMD%" (
    echo [ERROR] Python was installed but could not be found at %PY_INSTALL_DIR%
    echo Please close this window, open a new Command Prompt, and run install.bat again.
    pause
    exit /b 1
)
echo   [OK] Python 3.11 installed successfully.

:python_found
:: Confirm it's actually Python 3 (not a Python 2 remnant on PATH)
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info.major==3 else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Found Python installation is not Python 3.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%V"
echo   [OK] Found: %PY_VER% ^(using: %PYTHON_CMD%^)

:: -----------------------------------------------------------
:: Step 2: Detect all Python installations
:: -----------------------------------------------------------
echo.
echo [2/7] Detecting Python installations...
set "PYTHON_LIST=%TEMP%\python_installations.txt"
where python > "%PYTHON_LIST%" 2>nul
where py >> "%PYTHON_LIST%" 2>nul
set INSTALL_COUNT=0
for /f "delims=" %%p in ('type "%PYTHON_LIST%" 2^>nul') do (
    set /a INSTALL_COUNT+=1
)
echo   Total: !INSTALL_COUNT! Python executable(s) detected on PATH.

:: -----------------------------------------------------------
:: Step 3: Upgrade pip
:: -----------------------------------------------------------
echo.
echo [3/7] Updating pip...
%PYTHON_CMD% -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo   [WARNING] pip upgrade failed — continuing anyway.
) else (
    echo   [OK] pip is up to date.
)

:: -----------------------------------------------------------
:: Step 4: Install / upgrade Pillow separately (verbose on fail)
:: -----------------------------------------------------------
echo.
echo [4/7] Checking Pillow (image processing)...
%PYTHON_CMD% -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Pillow not found - installing...
    %PYTHON_CMD% -m pip install Pillow --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Pillow. Check your internet connection.
        pause
        exit /b 1
    )
    echo   [OK] Pillow installed.
) else (
    echo   [OK] Pillow present - upgrading if needed...
    %PYTHON_CMD% -m pip install --upgrade Pillow --quiet
)

:: -----------------------------------------------------------
:: Step 5: Install / upgrade remaining dependencies
:: -----------------------------------------------------------
echo.
echo [5/7] Installing remaining dependencies...
echo   (CustomTkinter, Requests, pywin32, emoji-country-flag, deep-translator)
%PYTHON_CMD% -m pip install --upgrade customtkinter requests pywin32 emoji-country-flag deep-translator --quiet
if %errorlevel% neq 0 (
    echo [ERROR] One or more dependencies failed to install.
    pause
    exit /b 1
)
echo   [OK] All dependencies installed.

:: -----------------------------------------------------------
:: Step 6: Verify imports
:: -----------------------------------------------------------
echo.
echo [6/7] Verifying installations...
%PYTHON_CMD% -c "import customtkinter; import PIL; import requests; import flag; import deep_translator; print('  [OK] All dependencies verified.')"
if %errorlevel% neq 0 (
    echo [ERROR] Verification failed — one or more packages may not have installed correctly.
    pause
    exit /b 1
)

:: -----------------------------------------------------------
:: Step 7: Launch BeamSkin Studio
:: -----------------------------------------------------------
echo.
echo [7/7] Starting BeamSkin Studio...
timeout /t 2 /nobreak >nul

if exist "BeamSkin Studio.bat" (
    start "" "BeamSkin Studio.bat"
    exit
)
if exist "Beamskin_studio.bat" (
    start "" "Beamskin_studio.bat"
    exit
)

echo.
echo ============================================================
echo  [ERROR] Could not find the BeamSkin Studio launcher.
echo ============================================================
echo.
echo  This usually means one of the following:
echo.
echo  1. The launcher file is missing from this folder.
echo     - Try launching it manually if it exists elsewhere
echo       in the BeamSkin Studio folder.
echo.
echo  2. The program files are incomplete or weren't fully downloaded.
echo     - Re-download BeamSkin Studio and run install.bat again
echo       from the newly extracted folder.
echo.
echo  3. If the issue persists, contact the developer:
echo       Email: burztworkshop@gmail.com
echo.
echo ============================================================
echo.
pause
exit
