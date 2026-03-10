@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: BeamSkin Studio Launcher
:: ============================================================

set "LOG_FILE=%TEMP%\BeamSkinStudio_launch.log"

:: Clear old log
if exist "%LOG_FILE%" del /f /q "%LOG_FILE%"

:: -----------------------------------------------------------
:: Step 1: Check Python is available
:: -----------------------------------------------------------
python --version >nul 2>&1
if %errorlevel% neq 0 (
    call :show_error "Python Not Found" "Python is not installed or not in PATH.^^Please run install.bat first."
    exit /b 1
)

:: -----------------------------------------------------------
:: Step 2: Check critical dependencies
:: -----------------------------------------------------------
python -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    call :show_error "Missing Dependency" "customtkinter is not installed.^^Please run install.bat to install dependencies."
    exit /b 1
)

python -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    call :show_error "Missing Dependency" "Pillow (PIL) is not installed.^^Please run install.bat to install dependencies."
    exit /b 1
)

python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    call :show_error "Missing Dependency" "requests is not installed.^^Please run install.bat to install dependencies."
    exit /b 1
)

:: -----------------------------------------------------------
:: Step 3: Check main files exist
:: -----------------------------------------------------------
if exist "launchers-scripts\quick_launcher.py" (
    set "LAUNCH_FILE=launchers-scripts\quick_launcher.py"
    goto :launch
)

if exist "main.py" (
    set "LAUNCH_FILE=main.py"
    goto :launch
)

call :show_error "Files Not Found" "Neither quick_launcher.py nor main.py could be found.^^Make sure you are running this from the BeamSkin Studio root folder.^^Expected location: %CD%"
exit /b 1

:: -----------------------------------------------------------
:: Step 4: Launch — capture output, detect crash
:: -----------------------------------------------------------
:launch
python "%LAUNCH_FILE%" > "%LOG_FILE%" 2>&1
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    call :show_error_with_log "BeamSkin Studio crashed on startup (Exit Code: %EXIT_CODE%)"
    exit /b %EXIT_CODE%
)

exit /b 0

:: -----------------------------------------------------------
:: :show_error  title  message
:: Simple popup for pre-launch errors (no log file needed)
:: -----------------------------------------------------------
:show_error
set "_TITLE=%~1"
set "_MSG=%~2"

python -c "import tkinter as tk; from tkinter import messagebox; r=tk.Tk(); r.withdraw(); messagebox.showerror('%_TITLE%', '%_MSG%'.replace('^^',chr(10))); r.destroy()" 2>nul

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] %_TITLE%
    echo %_MSG%
    pause
)
goto :eof

:: -----------------------------------------------------------
:: :show_error_with_log  title
:: Full scrollable log viewer popup for crashes
:: -----------------------------------------------------------
:show_error_with_log
set "_TITLE=%~1"

python -c ^
"import tkinter as tk; from tkinter import scrolledtext; import os, sys;" ^
"LOG=r'%LOG_FILE%';" ^
"root=tk.Tk(); root.title('BeamSkin Studio - Startup Error'); root.geometry('700x450'); root.configure(bg='#1a1a1a');" ^
"tk.Label(root,text='%_TITLE%',font=('Arial',11,'bold'),fg='#ff5555',bg='#1a1a1a',wraplength=670,justify='left').pack(pady=(12,2),padx=12,anchor='w');" ^
"tk.Label(root,text='Full error log shown below. Fix the issue and relaunch, or run install.bat.',font=('Arial',9),fg='#aaaaaa',bg='#1a1a1a',wraplength=670,justify='left').pack(padx=12,anchor='w');" ^
"st=scrolledtext.ScrolledText(root,font=('Consolas',8),bg='#0d0d0d',fg='#d4d4d4',wrap='word',insertbackground='white'); st.pack(fill='both',expand=True,padx=12,pady=8);" ^
"log=open(LOG).read() if os.path.exists(LOG) else 'Log file not found: '+LOG; st.insert('end',log); st.see('end');" ^
"bf=tk.Frame(root,bg='#1a1a1a'); bf.pack(fill='x',padx=12,pady=(0,10));" ^
"tk.Button(bf,text='Open Log File',command=lambda:os.startfile(LOG),bg='#333',fg='white',relief='flat',padx=10).pack(side='left');" ^
"tk.Button(bf,text='Close',command=root.destroy,bg='#555',fg='white',relief='flat',padx=10).pack(side='right');" ^
"root.mainloop()" 2>nul

if %errorlevel% neq 0 (
    echo.
    echo [CRASH] %_TITLE%
    echo Log saved to: %LOG_FILE%
    pause
)
goto :eof
