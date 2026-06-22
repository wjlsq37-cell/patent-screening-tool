@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

call :find_system_python
if errorlevel 1 goto no_python

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建本地 Python 环境...
  %SYSTEM_PYTHON% -m venv ".venv"
  if errorlevel 1 (
    echo 创建环境失败。
    pause
    exit /b 1
  )
)

echo 正在安装依赖...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto deps_failed
".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto deps_failed
".venv\Scripts\python.exe" -c "import uvicorn, fastapi, pandas, openpyxl, yaml, httpx, playwright"
if errorlevel 1 goto deps_failed

echo 安装完成。现在可以双击 start_windows.bat 启动。
pause
exit /b 0

:find_system_python
set "SYSTEM_PYTHON="
py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and sys.version_info[1] in range(11, 20) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "SYSTEM_PYTHON=py -3.13"
  exit /b 0
)
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and sys.version_info[1] in range(11, 20) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "SYSTEM_PYTHON=py -3.12"
  exit /b 0
)
py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and sys.version_info[1] in range(11, 20) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "SYSTEM_PYTHON=py -3.11"
  exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and sys.version_info[1] in range(11, 20) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "SYSTEM_PYTHON=python"
  exit /b 0
)
exit /b 1

:no_python
echo 未找到 Python 3.11 或更高版本。
echo 如需在没有 Python 的电脑上使用，请运行便携版 zip 中的 start_windows.bat。
pause
exit /b 1

:deps_failed
echo 依赖安装失败，请检查网络后重新运行本脚本。
pause
exit /b 1
