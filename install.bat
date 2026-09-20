@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo BeamSkin Studio - Dependency Installer
echo ============================================================
echo.

:: ── [0/7] Detect running from inside an unextracted ZIP/RAR ─────────────────
:: Archive managers (WinRAR, 7-Zip, Explorer's zip viewer) often run files
:: directly from a temp mount when the user double-clicks inside the
:: archive without extracting first. Catch that before anything else,
:: since every step after this will fail in confusing ways otherwise.
set "SCRIPT_DIR=%~dp0"
set "CUR_PATH=%SCRIPT_DIR%"
set "IS_ARCHIVE="

echo !CUR_PATH! | findstr /i /c:"\Rar$" >nul 2>&1
if !errorlevel! equ 0 set "IS_ARCHIVE=1"

echo !CUR_PATH! | findstr /i /c:".zip\" >nul 2>&1
if !errorlevel! equ 0 set "IS_ARCHIVE=1"

echo !CUR_PATH! | findstr /i /c:".rar\" >nul 2>&1
if !errorlevel! equ 0 set "IS_ARCHIVE=1"

echo !CUR_PATH! | findstr /i /c:".7z\" >nul 2>&1
if !errorlevel! equ 0 set "IS_ARCHIVE=1"

echo !CUR_PATH! | findstr /i /c:"\Temp\7z" >nul 2>&1
if !errorlevel! equ 0 set "IS_ARCHIVE=1"

:: Fallback heuristic: running from directly inside %TEMP% at all is a
:: strong sign this is still an archive mount, since nobody installs the
:: app there on purpose.
if not defined IS_ARCHIVE (
    echo !CUR_PATH! | findstr /i /c:"!TEMP!" >nul 2>&1
    if !errorlevel! equ 0 set "IS_ARCHIVE=1"
)

:: Strongest signal of all: a real extracted copy of BeamSkin Studio always
:: has main.py and requirements.txt sitting right next to this script. Their
:: absence means either the archive was never extracted, or the extraction
:: was incomplete/corrupted - either way, manual extraction is the fix.
if not exist "%SCRIPT_DIR%main.py" set "IS_ARCHIVE=1"
if not exist "%SCRIPT_DIR%requirements.txt" set "IS_ARCHIVE=1"

if defined IS_ARCHIVE (
    echo.
    echo ============================================================
    echo  [ERROR] You're running this from inside a ZIP/RAR archive!
    echo ============================================================
    echo.
    echo  It looks like you double-clicked a file INSIDE the archive
    echo  without extracting it first, or the extraction is incomplete.
    echo  This will not work correctly.
    echo.
    echo  Detected folder:
    echo    !CUR_PATH!
    echo.
    echo  To fix this:
    echo    1. Close this window.
    echo    2. Right-click the downloaded ZIP/RAR file itself.
    echo    3. Choose "Extract All..." ^(or "Extract Here" in WinRAR/7-Zip^).
    echo    4. Open the EXTRACTED folder ^(not the archive^) and run
    echo       Install.bat from there.
    echo.
    echo  Tip: avoid extracting into a path with spaces, e.g.
    echo       C:\Tools\BeamSkin works great.
    echo.
    pause
    exit /b 1
)

echo [OK] Running from a properly extracted folder.
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

call :install_if_missing "PIL"             "Pillow"          "Pillow - image processing"
call :install_if_missing "PySide6"         "PySide6"         "PySide6 - GUI framework"
call :install_if_missing "requests"        "requests"        "requests - HTTP"
call :install_if_missing "win32api"        "pywin32"         "pywin32 - Windows APIs"
call :install_if_missing "imageio"         "imageio"         "imageio - extended DDS/texture support"
call :install_if_missing "deep_translator" "deep-translator" "deep-translator - changelog translation"

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
            call :manual_fallback
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
%PY% -c "import PySide6; import PIL; import requests; import win32api; import imageio; import deep_translator; print('[OK] All core dependencies verified')"
if %errorlevel% neq 0 (
    call :manual_fallback
    exit /b 1
)

goto :do_launch

:: -----------------------------------------------------------
:: :manual_fallback
:: Shown whenever the automated install could not be verified.
:: Mirrors the "Manual Install" tab on the BeamSkin Studio website.
:: -----------------------------------------------------------
:manual_fallback
echo.
echo ============================================================
echo  [ERROR] Automatic installation could not be verified.
echo ============================================================
echo.
echo  Please install manually instead:
echo.
echo    1. Install Python 3.9+ (3.12 recommended) from:
echo       https://www.python.org/downloads/
echo       IMPORTANT: check "Add Python to PATH" during install.
echo.
echo    2. Open Command Prompt or PowerShell in this folder.
echo       (Tip: type cmd in Explorer's address bar while inside
echo       the BeamSkin Studio folder.)
echo.
echo    3. Run:
echo       pip install -r requirements.txt
echo       (If "pip" isn't found, try: python -m pip install -r requirements.txt)
echo.
echo  Common issues:
echo    - Windows Defender / SmartScreen warning: click
echo      "More info -^> Run anyway" - this is a false positive
echo      common with Python apps.
echo    - ModuleNotFoundError after this: re-run install.bat, or
echo      install the missing package manually with:
echo      pip install ^<package-name^>
echo    - Nothing works: delete this folder and the downloaded ZIP,
echo      then re-download a fresh copy and try again.
echo.
echo  Still stuck? Open an issue on GitHub with the error above:
echo    https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta/issues
echo  Or email: burztworkshop@gmail.com
echo.
pause
exit /b 1

:: ── [7/7] Launch BeamSkin Studio ────────────────────────────────────────────
:do_launch
echo [7/7] Starting BeamSkin Studio...
timeout /t 2 /nobreak >nul

if exist "%SCRIPT_DIR%Beamskin_studio.bat" (
    start "" "%SCRIPT_DIR%Beamskin_studio.bat"
    exit
)
if exist "%SCRIPT_DIR%BeamSkin Studio.bat" (
    start "" "%SCRIPT_DIR%BeamSkin Studio.bat"
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
