@echo off
setlocal
cd /d "%~dp0"

if exist "runtime\python\python.exe" (
  set "APP_PYTHON=runtime\python\python.exe"
) else (
  set "APP_PYTHON=.venv\Scripts\python.exe"
)

if not exist "%APP_PYTHON%" (
  call install_windows.bat
  if errorlevel 1 exit /b 1
  set "APP_PYTHON=.venv\Scripts\python.exe"
)

echo 正在启动 PatentHub AI 专利分析操作台...
echo 浏览器地址：http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
"%APP_PYTHON%" run.py
pause
