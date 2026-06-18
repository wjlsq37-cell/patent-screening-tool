@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call install_windows.bat
  if errorlevel 1 exit /b 1
)

echo 正在启动 PatentHub AI 专利分析操作台...
echo 浏览器地址：http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
".venv\Scripts\python.exe" run.py
pause

