@echo off
setlocal
chcp 65001 >nul
title Shionarium - close this window to stop services
cd /d "%~dp0backend"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
if not exist ".venv\Scripts\python.exe" (
  echo 尚未安装基础依赖，请先按 README 完成安装。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.desktop_shortcut --target "%~dp0启动 Shionarium.bat" --name Shionarium --icon "%~dp0assets\shionarium.ico"
".venv\Scripts\python.exe" -m app.launcher %*
if errorlevel 1 pause
