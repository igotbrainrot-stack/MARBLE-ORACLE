@echo off
rem Fallback Windows launcher for systems where VBScript (wscript.exe) is
rem disabled or removed. It starts the same setup window as the .vbs launcher.
setlocal
set "BOOT=%~dp0Application\Runtime\launch_suite.pyw"
if not exist "%BOOT%" (
  echo The application folder is missing. Extract the entire Marble Oracle ZIP.
  pause
  exit /b 2
)
cd /d "%~dp0Application\Runtime"
pyw -3 -c "import tkinter" >nul 2>&1
if not errorlevel 1 (
  start "" pyw -3 "%BOOT%"
  exit /b 0
)
pythonw -c "import tkinter" >nul 2>&1
if not errorlevel 1 (
  start "" pythonw "%BOOT%"
  exit /b 0
)
echo Python 3 with Tkinter is required before the setup window can appear.
echo Install Python 3 from https://www.python.org/downloads/windows/ then reopen Marble Oracle.
pause
exit /b 3
