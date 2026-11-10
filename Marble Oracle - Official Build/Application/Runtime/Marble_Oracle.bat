@echo off
cd /d "%~dp0"
py -3 "%~dp0Marble_Oracle.pyw" %*
if errorlevel 1 pause
