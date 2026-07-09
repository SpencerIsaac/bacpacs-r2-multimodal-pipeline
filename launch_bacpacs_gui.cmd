@echo off
cd /d "%~dp0"
call "%~dp0bacpacs.cmd" gui %*
if errorlevel 1 pause
