@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo 打包机需要先安装 Python 3.11 或更高版本。
  echo 目标使用电脑不需要安装 Python。
  pause
  exit /b 1
)

echo 正在生成免安装便携包...
python scripts\build_package.py --mode portable
if errorlevel 1 (
  echo 打包失败。
  pause
  exit /b 1
)

echo 打包完成，文件位于 dist 目录。
pause
