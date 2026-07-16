@echo off
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%bacpacs.ps1" %*
exit /b %ERRORLEVEL%
