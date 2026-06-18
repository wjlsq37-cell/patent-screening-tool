@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo 未找到 Python。请先安装 Python 3.11 或更高版本，然后重新运行本脚本。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建本地 Python 环境...
  python -m venv .venv
  if errorlevel 1 (
    echo 创建环境失败。
    pause
    exit /b 1
  )
)

echo 正在安装依赖...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

echo 安装完成。
pause

