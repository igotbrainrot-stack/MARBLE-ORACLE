@echo off
cd /d "%~dp0Marble_Oracle_App"
py -3 oracle_bootstrap.py --crt-v2 --retro %*
if errorlevel 1 pause
