@echo off
rem Open Oggcultist with visible diagnostic output and stop on failure.
rem Uses the WINDOWS LAUNCHER.bat that sits next to this "Oggcultist" folder.
cd /d "%~dp0"
call "%~dp0..\WINDOWS LAUNCHER.bat" --console
