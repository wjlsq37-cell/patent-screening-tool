@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:8000"
set "HEALTH_URL=http://127.0.0.1:8000/health"
set "APP_PYTHON="

if exist "%~dp0runtime\python\python.exe" (
  set "APP_PYTHON=%~dp0runtime\python\python.exe"
)

if not defined APP_PYTHON if exist "%~dp0.venv\Scripts\python.exe" (
  set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
)

if defined APP_PYTHON goto python_ready

echo 未找到本地 Python 运行环境，正在自动创建...
call :find_system_python
if errorlevel 1 goto no_python
%SYSTEM_PYTHON% -m venv ".venv"
if errorlevel 1 goto venv_failed
set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"

:python_ready

"%APP_PYTHON%" -c "import uvicorn, fastapi, pandas, openpyxl, yaml, httpx, playwright" >nul 2>nul
if errorlevel 1 (
  echo 正在安装或修复运行依赖，请稍等...
  "%APP_PYTHON%" -m pip install --upgrade pip
  if errorlevel 1 goto deps_failed
  "%APP_PYTHON%" -m pip install -r "backend\requirements.txt"
  if errorlevel 1 goto deps_failed
)

call :check_server
if errorlevel 1 (
  echo 正在启动 PatentHub AI 专利分析操作台...
  if not exist "backend\data" mkdir "backend\data"
  start "PatentHub AI 服务" /min cmd /c ""%APP_PYTHON%" run.py 1>>"backend\data\server.out.log" 2>>"backend\data\server.err.log""
  call :wait_server
  if errorlevel 1 goto start_failed
) else (
  echo 服务已在运行，将直接打开网页。
)

echo 浏览器地址：%APP_URL%
start "" "%APP_URL%"
echo 如果浏览器没有自动打开，请手动复制上面的地址到浏览器。
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

:check_server
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing '%HEALTH_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
exit /b %errorlevel%

:wait_server
for /l %%I in (1,1,45) do (
  call :check_server
  if not errorlevel 1 exit /b 0
  timeout /t 1 >nul
)
exit /b 1

:no_python
echo 未找到可用的 Python 3.11 或更高版本。
echo 如果你是在没有 Python 的电脑上使用，请解压并运行便携版 zip 中的 start_windows.bat。
pause
exit /b 1

:venv_failed
echo 创建本地 Python 环境失败。
pause
exit /b 1

:deps_failed
echo 依赖安装失败，请检查网络后重新运行本脚本。
pause
exit /b 1

:start_failed
echo 服务启动失败。请查看 backend\data\server.err.log 中的错误信息。
pause
exit /b 1
