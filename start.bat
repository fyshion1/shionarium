@echo off
chcp 65001 >nul
rem Compatibility entry; use the clearly named launcher beside this file.
call "%~dp0启动 Shionarium.bat" %*
exit /b %errorlevel%
