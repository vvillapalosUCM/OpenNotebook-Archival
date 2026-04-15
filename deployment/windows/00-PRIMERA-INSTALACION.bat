@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Install.ps1"
if errorlevel 1 pause
endlocal
