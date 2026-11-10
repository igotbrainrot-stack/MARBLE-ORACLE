@echo off
rem Build the portable Oggcultist.exe on Windows (needs Python 3.10+ with Tcl/Tk).
rem Output: dist\Oggcultist.exe, dist\Oggcultist-<version>-windows-x64-portable.zip, dist\SHA256SUMS.txt
rem Optional: pass --bundle-tools C:\path\to\ffmpeg\bin to embed FFmpeg (read docs\development\PACKAGING.md first).
setlocal EnableExtensions
cd /d "%~dp0\..\.."
if not exist ".venv-build\Scripts\python.exe" (
    py -3 -m venv .venv-build || python -m venv .venv-build || goto failed
)
".venv-build\Scripts\python.exe" -m pip install --upgrade pip || goto failed
".venv-build\Scripts\python.exe" -m pip install -r requirements.txt -r packaging\requirements-build.txt || goto failed
".venv-build\Scripts\python.exe" packaging\build.py %* || goto failed
echo.
echo Build complete. See the dist folder.
exit /b 0
:failed
echo.
echo Build failed. See the messages above.
exit /b 1
