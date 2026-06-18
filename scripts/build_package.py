from __future__ import annotations

import fnmatch
import zipfile
from datetime import datetime
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_DIR / "dist"

EXCLUDE_PATTERNS = [
    ".git/*",
    ".venv/*",
    "__pycache__/*",
    "*.pyc",
    "dist/*",
    "backend/config/config.yaml",
    "backend/data/history.json",
    "backend/data/server.*.log",
    "backend/data/uploads/*",
    "backend/data/outputs/*",
    "backend/data/cache/*",
]

KEEP_FILES = {
    "backend/data/uploads/.gitkeep",
    "backend/data/outputs/.gitkeep",
    "backend/data/cache/.gitkeep",
}


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def should_exclude(path: Path) -> bool:
    relative = rel(path)
    if relative in KEEP_FILES:
        return False
    return any(fnmatch.fnmatch(relative, pattern) for pattern in EXCLUDE_PATTERNS)


def read_local_api_key() -> str:
    config_path = PROJECT_DIR / "backend" / "config" / "config.yaml"
    if not config_path.exists():
        return ""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return str((data.get("ai") or {}).get("api_key") or "")


def assert_no_key_leak(zip_path: Path, api_key: str) -> None:
    if len(api_key) < 8:
        return
    key_bytes = api_key.encode("utf-8")
    with zipfile.ZipFile(zip_path) as zf:
        for item in zf.infolist():
            if item.file_size > 5_000_000:
                continue
            if key_bytes in zf.read(item.filename):
                raise RuntimeError(f"打包结果包含本地 API Key：{item.filename}")


def build_package() -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = DIST_DIR / f"PatentHub_AI_Assistant_{timestamp}.zip"
    root_name = PROJECT_DIR.name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in PROJECT_DIR.rglob("*"):
            if path.is_dir() or should_exclude(path):
                continue
            arcname = f"{root_name}/{rel(path)}"
            zf.write(path, arcname)

    assert_no_key_leak(zip_path, read_local_api_key())
    return zip_path


if __name__ == "__main__":
    package = build_package()
    print(package)

