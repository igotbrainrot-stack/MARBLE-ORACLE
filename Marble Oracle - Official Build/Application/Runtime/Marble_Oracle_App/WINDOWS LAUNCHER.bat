@echo off
rem Oggcultist launcher for Windows. Keep this file next to the "Oggcultist" folder.
rem   WINDOWS LAUNCHER.bat            prepare Python, then open Oggcultist with monitored startup
rem On first start: if no Python 3.10+ with Tkinter is found it offers to install Python 3.12
rem (winget, asks first), then creates .venv and downloads Mutagen and Pillow into it.
rem   WINDOWS LAUNCHER.bat --console  troubleshooting: keep this window open and show all messages
rem Everything (the program, its private Python environment .venv) stays inside the
rem "Oggcultist" folder; this launcher only switches into it.
rem Oggcultist.pyw supervises the GUI startup and displays an error if it fails.
rem No VBScript/Windows Script Host or PowerShell is used.
setlocal EnableExtensions
set "OGGCULTIST_HOME=%~dp0Oggcultist"
if not exist "%OGGCULTIST_HOME%\launch.py" goto missing_folder
cd /d "%OGGCULTIST_HOME%"
title Oggcultist - Startup

set "OGGCULTIST_CONSOLE="
if /i "%~1"=="--console" (
    set "OGGCULTIST_CONSOLE=1"
    shift
)

echo.
echo ==========================================
echo   Oggcultist - Music Player and Converter
echo ==========================================
echo.
echo [1/3] Preparing Python...
rem A usable Python is 3.10+ with Tkinter (the window) and venv. python.org installers include both.
set "OGG_CHECK=import sys, tkinter, venv; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)"

rem An environment from an earlier start that is broken (or lacks Tkinter) is rebuilt.
if not exist ".venv\Scripts\python.exe" goto need_venv
".venv\Scripts\python.exe" -c "import pip, tkinter" >nul 2>&1
if not errorlevel 1 goto venv_ready
echo The private Python environment is incomplete; rebuilding it.
rmdir /s /q ".venv"

:need_venv
call :find_python
if defined OGG_PYTHON goto make_venv
call :offer_python
call :find_python
if not defined OGG_PYTHON goto no_python

:make_venv
echo Creating the private Python environment (first start only)...
%OGG_PYTHON% -m venv .venv
if errorlevel 1 goto startup_error

:venv_ready
echo.
echo [2/3] Checking Python dependencies (Mutagen and Pillow; downloaded on first start)...
".venv\Scripts\python.exe" -c "import mutagen, PIL" >nul 2>&1
if not errorlevel 1 goto deps_ready
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto startup_error
:deps_ready

echo.
echo [3/3] Launching Oggcultist...
if defined OGGCULTIST_CONSOLE goto console_launch
if not exist ".venv\Scripts\pythonw.exe" goto startup_error

rem Normal use: launch the monitored windowless bootstrap. Unlike running
rem launch.py directly under pythonw, Oggcultist.pyw waits for the GUI process
rem and reports startup failures through a Windows dialog plus launcher.log.
rem Double-check the script exists, and keep all paths rooted at the Oggcultist folder.
rem START returns immediately, then EXIT /B closes this command window while Oggcultist runs.
if not exist "Oggcultist.pyw" goto startup_error
start "" ".venv\Scripts\pythonw.exe" "%OGGCULTIST_HOME%\Oggcultist.pyw"
if errorlevel 1 goto startup_error
exit /b 0

:console_launch
echo If FFmpeg is not installed, Oggcultist will offer to install it now.
echo After installation, the desktop window should open automatically.
echo.
rem All setup and the GUI run in one Python process. Do not add a separate FFmpeg
rem setup step here: it would lose the process-local PATH changes and hide status.
".venv\Scripts\python.exe" -u launch.py %1 %2 %3 %4 %5 %6 %7 %8 %9
set "OGGCULTIST_EXIT=%ERRORLEVEL%"
if not "%OGGCULTIST_EXIT%"=="0" goto app_error

echo.
echo Oggcultist has closed.
exit /b 0

:startup_error
echo.
echo ERROR: Oggcultist could not prepare Python. See the message above.
echo The first start needs the internet once, to download Mutagen and Pillow.
pause
exit /b 1

:no_python
echo.
echo ERROR: No suitable Python was found.
echo Oggcultist needs Python 3.10 or newer from python.org, with "tcl/tk and IDLE" ticked
echo (it is ticked by default). Download it from https://www.python.org/downloads/windows/
echo then start Oggcultist again.
pause
exit /b 1

rem ---------------------------------------------------------------------------------------
rem :find_python sets OGG_PYTHON to a command for a Python 3.10+ with Tkinter and venv.
rem Checks the py launcher, python on PATH, then the standard per-user and all-users folders
rem (the last two find a Python that winget has just installed, before PATH is refreshed).
:find_python
set "OGG_PYTHON="
where py >nul 2>&1
if errorlevel 1 goto find_on_path
py -3 -c "%OGG_CHECK%" >nul 2>&1
if not errorlevel 1 set "OGG_PYTHON=py -3"
if defined OGG_PYTHON exit /b 0
:find_on_path
where python >nul 2>&1
if errorlevel 1 goto find_in_folders
python -c "%OGG_CHECK%" >nul 2>&1
if not errorlevel 1 set "OGG_PYTHON=python"
if defined OGG_PYTHON exit /b 0
:find_in_folders
for %%V in (313 312 311 310) do call :try_python "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
for %%V in (313 312 311 310) do call :try_python "%ProgramFiles%\Python%%V\python.exe"
exit /b 0

:try_python
if defined OGG_PYTHON exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "%OGG_CHECK%" >nul 2>&1
if not errorlevel 1 set "OGG_PYTHON="%~1""
exit /b 0

rem :offer_python asks, then installs Python 3.12 for this Windows user with winget
rem (Microsoft's own installer tool; no administrator rights needed).
:offer_python
echo.
echo Oggcultist needs Python 3.10 or newer (with Tkinter), and none was found.
where winget >nul 2>&1
if errorlevel 1 exit /b 0
echo It can install Python 3.12 from python.org for you now, using Windows' winget.
choice /c YN /m "Install Python 3.12 now"
if errorlevel 2 exit /b 0
winget install --exact --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
exit /b 0

:app_error
echo.
echo ERROR: Oggcultist could not open or exited with an error.
echo Please send the error above or the logs in %LOCALAPPDATA%\Oggcultist\logs when reporting the issue.
echo The window is being kept open so you can read the message.
pause
exit /b %OGGCULTIST_EXIT%
exit /b 1

:missing_folder
echo.
echo ERROR: The "Oggcultist" folder was not found next to this launcher.
echo Keep "WINDOWS LAUNCHER.bat" in the same folder as the "Oggcultist" folder,
echo exactly as they came out of the ZIP, and try again.
pause
exit /b 1
