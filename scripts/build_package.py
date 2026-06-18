from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = DIST_DIR / "_build"
CACHE_DIR = DIST_DIR / "_cache"
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
PYTHON_FTP_ROOT = "https://www.python.org/ftp/python"

EXCLUDE_PATTERNS = [
    ".git/*",
    ".venv/*",
    "__pycache__/*",
    "*.pyc",
    "dist/*",
    "runtime/*",
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


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.links.append(value)


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def should_exclude(path: Path) -> bool:
    relative = rel(path)
    if relative in KEEP_FILES:
        return False
    return any(fnmatch.fnmatch(relative, pattern) for pattern in EXCLUDE_PATTERNS)


def read_local_secrets() -> list[str]:
    config_path = PROJECT_DIR / "backend" / "config" / "config.yaml"
    if not config_path.exists():
        return []
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    ai = data.get("ai") or {}
    patenthub = data.get("patenthub") or {}
    return [
        str(ai.get("api_key") or ""),
        str(patenthub.get("username") or ""),
        str(patenthub.get("password") or ""),
    ]


def assert_no_secret_leak(zip_path: Path, secrets: list[str]) -> None:
    secret_bytes = [secret.encode("utf-8") for secret in secrets if len(secret) >= 8]
    if not secret_bytes:
        return
    with zipfile.ZipFile(zip_path) as zf:
        for item in zf.infolist():
            if item.file_size > 10_000_000:
                continue
            content = zf.read(item.filename)
            if any(secret in content for secret in secret_bytes):
                raise RuntimeError(f"打包结果包含本地敏感配置：{item.filename}")


def read_url_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_links(html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def version_key(version: str) -> tuple[int, int, int]:
    major, minor, micro = version.split(".")
    return int(major), int(minor), int(micro)


def available_minor_versions() -> list[str]:
    html = read_url_text(f"{PYTHON_FTP_ROOT}/")
    prefix = f"{sys.version_info.major}.{sys.version_info.minor}."
    versions = []
    for link in parse_links(html):
        version = link.strip("/")
        if version.startswith(prefix) and version.count(".") == 2:
            versions.append(version)
    return sorted(set(versions), key=version_key, reverse=True)


def resolve_python_embed_download() -> tuple[str, str]:
    candidates = [PYTHON_VERSION]
    candidates.extend(version for version in available_minor_versions() if version not in candidates)

    for version in candidates:
        directory_url = f"{PYTHON_FTP_ROOT}/{version}/"
        try:
            links = parse_links(read_url_text(directory_url))
        except Exception:
            continue

        preferred_names = [
            f"python-{version}-embed-amd64.zip",
            f"python-{version}-embeddable-amd64.zip",
        ]
        for name in preferred_names:
            if name in links:
                return version, f"{directory_url}{name}"

    raise RuntimeError(
        f"没有找到 Python {sys.version_info.major}.{sys.version_info.minor} 的 Windows embeddable amd64 运行时。"
    )


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(source_dir.parent).as_posix())


def copy_clean_source(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    for path in PROJECT_DIR.rglob("*"):
        if path.is_dir() or should_exclude(path):
            continue
        destination = target_dir / rel(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def download_python_embed() -> tuple[str, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    embed_version, embed_url = resolve_python_embed_download()
    archive = CACHE_DIR / Path(embed_url).name
    if archive.exists() and archive.stat().st_size > 1_000_000:
        return embed_version, archive

    print(f"下载便携 Python：{embed_url}")
    with urllib.request.urlopen(embed_url, timeout=120) as response:
        archive.write_bytes(response.read())
    return embed_version, archive


def prepare_portable_python(target_dir: Path) -> Path:
    python_dir = target_dir / "runtime" / "python"
    python_dir.mkdir(parents=True, exist_ok=True)

    embed_version, archive = download_python_embed()
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(python_dir)

    site_packages = python_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    pth_files = list(python_dir.glob("python*._pth"))
    if not pth_files:
        raise RuntimeError("未找到 Python embeddable 的 ._pth 文件。")
    pth_files[0].write_text(
        f"python{sys.version_info.major}{sys.version_info.minor}.zip\n"
        ".\n"
        "..\\..\n"
        "Lib\\site-packages\n"
        "import site\n",
        encoding="utf-8",
    )
    (target_dir / "runtime" / "PYTHON_VERSION.txt").write_text(
        f"Python {embed_version} embeddable amd64\n",
        encoding="utf-8",
    )

    requirements = target_dir / "backend" / "requirements.txt"
    print("安装依赖到便携运行环境...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-warn-script-location",
            "--target",
            str(site_packages),
            "-r",
            str(requirements),
        ],
        check=True,
    )
    return python_dir / "python.exe"


def build_source_package(timestamp: str, secrets: list[str]) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    zip_path = DIST_DIR / f"PatentHub_AI_Assistant_source_{timestamp}.zip"
    root_dir = BUILD_DIR / PROJECT_DIR.name
    copy_clean_source(root_dir)
    zip_directory(root_dir, zip_path)
    assert_no_secret_leak(zip_path, secrets)
    return zip_path


def build_portable_package(timestamp: str, secrets: list[str]) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    root_dir = BUILD_DIR / f"{PROJECT_DIR.name}-portable"
    copy_clean_source(root_dir)
    python_exe = prepare_portable_python(root_dir)
    runtime_version = (root_dir / "runtime" / "PYTHON_VERSION.txt").read_text(encoding="utf-8").split()[1]
    zip_path = DIST_DIR / f"PatentHub_AI_Assistant_portable_win_amd64_py{runtime_version.replace('.', '')}_{timestamp}.zip"

    subprocess.run(
        [
            str(python_exe),
            "-c",
            "import fastapi, uvicorn, pandas, openpyxl, yaml, httpx; "
            "from playwright.async_api import async_playwright; "
            "print('portable ok')",
        ],
        cwd=root_dir,
        check=True,
    )

    zip_directory(root_dir, zip_path)
    assert_no_secret_leak(zip_path, secrets)
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 PatentHub AI Assistant 分发包。")
    parser.add_argument(
        "--mode",
        choices=["portable", "source", "all"],
        default="portable",
        help="portable=内置便携 Python；source=源码包；all=两者都生成。默认 portable。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    secrets = read_local_secrets()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    packages: list[Path] = []
    if args.mode in {"source", "all"}:
        packages.append(build_source_package(timestamp, secrets))
    if args.mode in {"portable", "all"}:
        packages.append(build_portable_package(timestamp, secrets))

    print("打包完成：")
    for package in packages:
        print(package)


if __name__ == "__main__":
    main()
