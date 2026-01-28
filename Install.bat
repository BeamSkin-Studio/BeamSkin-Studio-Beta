@echo off
setlocal enabledelayedexpansion

:: BeamSkin Studio - Dependency Installer
:: This script installs Python and all required packages for BeamSkin Studio

echo ============================================================
echo BeamSkin Studio - Dependency Installer
echo ============================================================
echo.

:: Check if Python is installed
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python is not installed or not in PATH!
    echo.
    echo Do you want to download and install Python automatically?
    echo.
    choice /C YN /M "Install Python now"
    if errorlevel 2 (
        echo.
        echo Installation cancelled.
        echo.
        echo To install manually, visit: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation!
        echo.
        pause
        exit /b 1
    )
    
    echo.
    echo ============================================================
    echo Installing Python...
    echo ============================================================
    echo.
    
    :: Create temp directory
    if not exist "%TEMP%\BeamSkinStudio" mkdir "%TEMP%\BeamSkinStudio"
    cd /d "%TEMP%\BeamSkinStudio"
    
    :: Download Python installer
    echo Downloading Python 3.11 installer...
    echo This may take a few minutes depending on your internet connection...
    echo.
    
    :: Using PowerShell to download Python installer
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'}"
    
    if not exist "python_installer.exe" (
        echo [ERROR] Failed to download Python installer!
        echo.
        echo Please download and install Python manually from:
        echo https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    
    echo [OK] Python installer downloaded successfully
    echo.
    echo Installing Python with automatic PATH configuration...
    echo This will take a few minutes...
    echo.
    
    :: Install Python silently with PATH and all users
    :: Using more reliable installation parameters
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1
    
    set INSTALL_EXIT_CODE=%errorlevel%
    
    :: Clean up installer
    del python_installer.exe
    
    if !INSTALL_EXIT_CODE! neq 0 (
        echo [WARNING] Automated installation encountered an issue.
        echo.
        echo Please install Python manually:
        echo 1. Download from: https://www.python.org/downloads/
        echo 2. Run the installer
        echo 3. CHECK the box "Add Python to PATH"
        echo 4. Complete the installation
        echo 5. Run this installer again
        echo.
        pause
        exit /b 1
    )
    
    echo [OK] Python installation completed
    echo.
    
    :: Python was just installed - need to restart the script to pick up new PATH
    echo ============================================================
    echo Python has been installed successfully!
    echo ============================================================
    echo.
    echo The installer needs to restart to detect the new Python installation.
    echo.
    echo Press any key to restart the installer...
    pause >nul
    
    :: Restart this script in a new command prompt (which will have the updated PATH)
    start "" "%~f0"
    exit
)

python --version
echo [OK] Python is installed
echo.

:: Check if pip is available
echo [2/6] Checking pip installation...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not available!
    echo.
    echo Installing pip...
    python -m ensurepip --default-pip
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install pip!
        pause
        exit /b 1
    )
)

python -m pip --version
echo [OK] pip is available
echo.

:: Upgrade pip
echo [3/6] Upgrading pip to latest version...
python -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Failed to upgrade pip, continuing anyway...
)
echo [OK] pip upgraded
echo.

:: Install required packages
echo [4/6] Installing required packages...
echo.
echo This may take a few minutes...
echo.

:: Core GUI framework
echo Installing CustomTkinter (GUI framework)...
python -m pip install customtkinter --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install customtkinter!
    pause
    exit /b 1
)
echo [OK] CustomTkinter installed

:: Image processing
echo Installing Pillow (image processing)...
python -m pip install Pillow --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Pillow!
    pause
    exit /b 1
)
echo [OK] Pillow installed

:: HTTP requests for update checker
echo Installing requests (HTTP library)...
python -m pip install requests --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requests!
    pause
    exit /b 1
)
echo [OK] requests installed

:: Optional dependencies
echo.
echo [5/6] Installing optional dependencies...
echo.

:: pywin32 for window manipulation (optional)
echo Installing pywin32 (Windows integration)...
python -m pip install pywin32 --quiet
if %errorlevel% neq 0 (
    echo [WARNING] pywin32 installation failed (optional dependency)
) else (
    echo [OK] pywin32 installed
)

:: Verify installations
echo.
echo [6/6] Verifying installations...
echo.

python -c "import customtkinter; print('[OK] CustomTkinter version:', customtkinter.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] CustomTkinter verification failed!
    pause
    exit /b 1
)

python -c "import PIL; print('[OK] Pillow version:', PIL.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Pillow verification failed!
    pause
    exit /b 1
)

python -c "import requests; print('[OK] Requests version:', requests.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Requests verification failed!
    pause
    exit /b 1
)

:: Check for pywin32 (optional)
python -c "import win32gui; print('[OK] pywin32 installed')" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] pywin32 not available (optional)
)

echo.
echo ============================================================
echo Installation Complete!
echo ============================================================
echo.
echo All required dependencies have been installed successfully.
echo.
echo ============================================================
echo.
echo Starting BeamSkin Studio...
echo.

:: Wait a moment before launching
timeout /t 2 /nobreak >nul

:: Launch BeamSkin Studio and close the installer window
if exist "BeamSkin Studio.bat" (
    echo Launching BeamSkin Studio...
    start "" "BeamSkin Studio.bat"
    exit
) else (
    echo [WARNING] Could not find "BeamSkin Studio.bat"
    echo Please run the application manually using:
    echo   - Double-click "BeamSkin Studio.bat"
    echo.
    pause
    exit
)
