@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: BeamSkin Studio Launcher
:: ============================================================

set "LOG_FILE=%TEMP%\BeamSkinStudio_launch.log"

:: Clear old log
if exist "%LOG_FILE%" del /f /q "%LOG_FILE%"

:: -----------------------------------------------------------
:: Step 1: Find a Python version that has all dependencies
:: Probes py launcher versions in preference order, then falls
:: back to plain "python" for installs not registered with py.
:: -----------------------------------------------------------
echo Detecting compatible Python installation...
set "PYEXE="

for %%V in (3.13 3.12 3.11 3.10 3.9) do (
    if not defined PYEXE (
        py -%%V --version >nul 2>&1
        if !errorlevel! equ 0 (
            py -%%V -c "import PySide6, PIL, requests, win32api, imageio" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYEXE=py -%%V"
                echo Found compatible Python %%V with all dependencies.
            )
        )
    )
)

:: Fallback: plain "python" (covers installs not registered with py launcher)
if not defined PYEXE (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        python -c "import PySide6, PIL, requests, win32api, imageio" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYEXE=python"
            echo Found compatible Python via system PATH.
        )
    )
)

if not defined PYEXE (
    call :show_error "No Compatible Python Found" "No Python installation with all required dependencies was found.^^Please run install.bat to install dependencies."
    exit /b 1
)

:: -----------------------------------------------------------
:: Step 2: Locate the entry point
:: -----------------------------------------------------------
if exist "launchers-scripts\launcher.py" (
    set "LAUNCH_FILE=launchers-scripts\launcher.py"
    goto :launch
)

if exist "main.py" (
    set "LAUNCH_FILE=main.py"
    goto :launch
)

call :show_error "Files Not Found" "Neither launcher.py nor main.py could be found.^^Make sure you are running this from the BeamSkin Studio root folder.^^Expected location: %CD%"
exit /b 1

:: -----------------------------------------------------------
:: Step 3: Launch via VBScript — no console, full crash guard
:: -----------------------------------------------------------
:launch
set "ABS_LAUNCH=%CD%\%LAUNCH_FILE%"
set "ABS_WORKDIR=%CD%"

:: Resolve actual python.exe path from whichever command was selected
for /f "delims=" %%P in ('%PYEXE% -c "import sys; print(sys.executable)"') do set "RESOLVED_PYEXE=%%P"

set "VBS=%TEMP%\BeamSkinStudio_launch.vbs"

> "%VBS%" (
    echo Set ws = CreateObject^("WScript.Shell"^)
    echo ws.CurrentDirectory = "%ABS_WORKDIR%"
    echo ec = ws.Run^(Chr^(34^) ^& "%RESOLVED_PYEXE%" ^& Chr^(34^) ^& " " ^& Chr^(34^) ^& "%ABS_LAUNCH%" ^& Chr^(34^), 0, True^)
    echo If ec ^<^> 0 Then MsgBox "BeamSkin Studio crashed ^(Exit Code: " ^& ec ^& "^)." ^& Chr^(10^) ^& Chr^(10^) ^& "Run install.bat to repair dependencies.", 16, "BeamSkin Studio - Error"
)

start "" /B wscript.exe "%VBS%"
exit /b 0

:: -----------------------------------------------------------
:: :show_error  title  message
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
