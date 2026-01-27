@echo off
REM Clear All Cache for BeamSkin Studio
REM This script removes all cache files and temporary data

echo ========================================
echo BeamSkin Studio - Clear Cache
echo ========================================
echo.

REM Change to parent directory (main program folder)
cd /d "%~dp0\.."

echo Current directory: %CD%
echo.

echo Current directory: %CD%
echo.

echo WARNING: This will delete the following:
echo   - Python __pycache__ folders
echo   - .pyc and .pyo files
echo   - Temporary files
echo   - Log files (if any)
echo   - Generated preview images (if any)
echo.
echo Your settings and projects will NOT be deleted.
echo.

set /p CONFIRM="Are you sure you want to continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo.
    echo Operation cancelled.
    pause
    exit /b 0
)

echo.
echo ========================================
echo Clearing Cache...
echo ========================================
echo.

set "DELETED_COUNT=0"

REM Delete Python cache folders (__pycache__)
echo [1/5] Removing Python cache folders...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo   Deleting: %%d
        rd /s /q "%%d" 2>nul
        if not exist "%%d" set /a DELETED_COUNT+=1
    )
)

REM Delete .pyc files
echo.
echo [2/5] Removing compiled Python files (.pyc)...
for /r . %%f in (*.pyc) do (
    if exist "%%f" (
        echo   Deleting: %%f
        del /f /q "%%f" 2>nul
        if not exist "%%f" set /a DELETED_COUNT+=1
    )
)

REM Delete .pyo files
echo.
echo [3/5] Removing optimized Python files (.pyo)...
for /r . %%f in (*.pyo) do (
    if exist "%%f" (
        echo   Deleting: %%f
        del /f /q "%%f" 2>nul
        if not exist "%%f" set /a DELETED_COUNT+=1
    )
)

REM Delete temporary preview images (if they exist)
echo.
echo [4/5] Checking for temporary files...
if exist "temp" (
    echo   Deleting temp folder...
    rd /s /q "temp" 2>nul
    if not exist "temp" set /a DELETED_COUNT+=1
)
if exist "cache" (
    echo   Deleting cache folder...
    rd /s /q "cache" 2>nul
    if not exist "cache" set /a DELETED_COUNT+=1
)
if exist "*.tmp" (
    echo   Deleting .tmp files...
    del /f /q "*.tmp" 2>nul
    set /a DELETED_COUNT+=1
)

REM Delete log files (optional)
echo.
echo [5/5] Checking for log files...
if exist "*.log" (
    set /p DELETE_LOGS="Found log files. Delete them? (Y/N): "
    if /i "!DELETE_LOGS!"=="Y" (
        for %%f in (*.log) do (
            echo   Deleting: %%f
            del /f /q "%%f" 2>nul
            if not exist "%%f" set /a DELETED_COUNT+=1
        )
    )
) else (
    echo   No log files found.
)

REM Delete Windows thumbnail cache (optional, in current directory only)
if exist "Thumbs.db" (
    echo   Deleting Thumbs.db...
    del /f /q /a "Thumbs.db" 2>nul
)
if exist "desktop.ini" (
    attrib -h -s "desktop.ini" 2>nul
    del /f /q "desktop.ini" 2>nul
)

echo.
echo ========================================
echo Cache Cleared Successfully!
echo ========================================
echo.
echo Summary:
echo   - Python cache: Removed
echo   - Compiled files: Removed
echo   - Temporary files: Removed
echo.
echo Your BeamSkin Studio is now cache-free!
echo.
echo Note: Some cache files will be recreated
echo automatically when you run the application.
echo.
pause
