from __future__ import annotations

import os

try:
    import uvicorn
except ModuleNotFoundError as exc:
    if exc.name == "uvicorn":
        print("缺少运行依赖 uvicorn。")
        print("Windows 用户请先双击 install_windows.bat 安装依赖，然后双击 start_windows.bat 启动。")
        print("也可以在当前目录运行：")
        print("  python -m pip install -r backend\\requirements.txt")
        print("安装完成后再运行：")
        print("  python run.py")
        raise SystemExit(1) from exc
    raise


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=False)
