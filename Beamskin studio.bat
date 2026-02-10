@echo off
:: BeamSkin Studio - Quick Launcher with Loading Screen
:: This version shows a loading GUI while the main app starts

:: Check if quick_launcher.py exists
if exist "launchers-scripts\quick_launcher.py" (
    start "" pythonw "launchers-scripts\quick_launcher.py"
    exit
) else (
    echo Error: quick_launcher.py not found in launchers-scripts folder!
    echo.
    echo Expected path: %CD%\launchers-scripts\quick_launcher.py
    echo.
    echo Falling back to direct launch...
    
    if exist "main.py" (
        start "" pythonw main.py
        exit
    ) else (
        echo main.py also not found!
        echo Please run this batch file from the BeamSkin Studio root folder.
        pause
        exit /b 1
    )
)