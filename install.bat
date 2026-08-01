@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo BeamSkin Studio - Dependency Installer
echo ============================================================
echo.

:: ── [1/7] Find a compatible Python (3.9 – 3.13) via py launcher ─────────────
echo [1/7] Detecting compatible Python installation...
set "PY="

for %%V in (3.13 3.12 3.11 3.10 3.9) do (
    if not defined PY (
        py -%%V --version >nul 2>&1
        if !errorlevel! equ 0 (
            py -%%V -c "import sys; exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY=py -%%V"
                echo [OK] Found Python %%V via py launcher.
            )
        )
    )
)

:: Fallback: plain "python" for installs not registered with the py launcher
if not defined PY (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        python -c "import sys; exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY=python"
            echo [OK] Found compatible Python via system PATH.
        ) else (
            echo [WARNING] Python on PATH is older than 3.9 - skipping.
        )
    )
)

:: Nothing found — download and install Python 3.11 then re-probe
if not defined PY (
    echo [WARNING] No compatible Python found ^(3.9+^).
    echo.
    echo Downloading and installing Python 3.11...
    if not exist "%TEMP%\BeamSkinStudio" mkdir "%TEMP%\BeamSkinStudio"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\BeamSkinStudio\python_installer.exe'}"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to download Python installer. Check your internet connection.
        pause
        exit /b 1
    )
    start /wait "" "%TEMP%\BeamSkinStudio\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1
    :: Refresh PATH so py launcher can see the new install
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%B"
    set "PATH=!SYS_PATH!;!USR_PATH!"
    py -3.11 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY=py -3.11"
        echo [OK] Python 3.11 installed successfully.
    ) else (
        echo Relaunching installer in a fresh shell to pick up new PATH...
        start "" cmd /c ""%~f0""
        exit
    )
)

:: ── [2/7] Report detected version ───────────────────────────────────────────
echo [2/7] Confirming Python version...
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set PY_VER=%%v
echo [OK] Using Python !PY_VER!  ^(!PY!^)

:: ── [3/7] Count all Python installs ─────────────────────────────────────────
echo [3/7] Detecting Python installations...
set INSTALL_COUNT=0
for /f "delims=" %%p in ('where python 2^>nul') do set /a INSTALL_COUNT+=1
echo Total: !INSTALL_COUNT! Python installation(s) detected on PATH.

:: ── [4/7] Upgrade pip ───────────────────────────────────────────────────────
echo [4/7] Auto-updating pip...
%PY% -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo [WARNING] pip upgrade failed - continuing anyway...
)

:: ── [5/7] Install / upgrade dependencies ────────────────────────────────────
echo [5/7] Installing / upgrading required dependencies...

call :install_if_missing "PIL"      "Pillow"   "Pillow - image processing"
call :install_if_missing "PySide6"  "PySide6"  "PySide6 - GUI framework"
call :install_if_missing "requests" "requests" "requests - HTTP"
call :install_if_missing "win32api" "pywin32"  "pywin32 - Windows APIs"
call :install_if_missing "imageio"  "imageio"  "imageio - extended DDS/texture support"

:: imageio plugin for DDS variants (BC7 / DX10 etc.)
echo   Checking imageio-ffmpeg (DDS plugin)...
%PY% -c "import imageio; imageio.plugins.freeimage.download()" >nul 2>&1
%PY% -m pip install --upgrade imageio[ffmpeg] --quiet >nul 2>&1

goto :after_helpers

:install_if_missing
    set "_label=%~3"
    echo   Checking !_label!...
    %PY% -c "import %~1" >nul 2>&1
    if !errorlevel! neq 0 (
        echo   Not found - installing %~2...
        %PY% -m pip install %~2 --quiet
        if !errorlevel! neq 0 (
            echo [ERROR] Failed to install %~2!
            pause
            exit /b 1
        )
        echo   [OK] %~2 installed.
    ) else (
        echo   [OK] !_label! already present - skipping.
    )
    exit /b 0

:after_helpers

:: ── [6/7] Verify all core imports ───────────────────────────────────────────
echo [6/7] Verifying installation...
%PY% -c "import PySide6; import PIL; import requests; import win32api; import imageio; print('[OK] All core dependencies verified')"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Dependency verification failed!
    echo         Check the error printed above, then run install.bat again.
    pause
    exit /b 1
)

:: ── [7/7] Launch BeamSkin Studio ────────────────────────────────────────────
echo [7/7] Starting BeamSkin Studio...
timeout /t 2 /nobreak >nul

if exist "Beamskin_studio.bat" (
    start "" "Beamskin_studio.bat"
    exit
)
if exist "BeamSkin Studio.bat" (
    start "" "BeamSkin Studio.bat"
    exit
)

echo.
echo ============================================================
echo  [ERROR] Could not find the BeamSkin Studio launcher bat.
echo ============================================================
echo.
echo  Make sure you are running install.bat from the BeamSkin
echo  Studio root folder (where main.py lives).
echo.
echo  If the issue persists, contact: burztworkshop@gmail.com
echo.
pause
exit /b 1
