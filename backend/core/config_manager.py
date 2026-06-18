from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
CACHE_DIR = DATA_DIR / "cache"
HISTORY_PATH = DATA_DIR / "history.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "ai": {
        "api_type": "OpenAI-compatible",
        "base_url": "https://api.openai.com",
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 1800,
        "stream": False,
        "timeout_seconds": 60,
    },
    "analysis": {
        "weights": {
            "relevance": 0.50,
            "legal_status": 0.20,
            "applicant": 0.15,
            "time": 0.10,
            "completeness": 0.05,
        },
        "high_relevance_threshold": 75,
        "max_ai_summary": 10,
        "important_applicants": [],
        "company_keywords": ["公司", "集团", "股份", "有限", "Corporation", "Inc", "Ltd"],
        "research_keywords": ["大学", "学院", "研究院", "科学院", "研究所"],
    },
    "export": {
        "filename_prefix": "PatentHub_AI分析",
        "timezone": "Asia/Shanghai",
    },
    "patenthub": {
        "base_url": "https://www.patenthub.cn",
        "username": "",
        "password": "",
    },
    "automation": {
        "default_download_limit": 100,
        "max_download_limit": 500,
        "browser_channel": "msedge",
        "headless": False,
    },
}


def ensure_data_dirs() -> None:
    for directory in (UPLOAD_DIR, OUTPUT_DIR, CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def read_yaml(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or deepcopy(default)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def load_config() -> dict[str, Any]:
    ensure_data_dirs()
    path = CONFIG_DIR / "config.yaml"
    loaded = read_yaml(path, {})
    config = _deep_merge(DEFAULT_CONFIG, loaded)
    if not path.exists():
        write_yaml(path, config)
    return config


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(DEFAULT_CONFIG, config)
    write_yaml(CONFIG_DIR / "config.yaml", merged)
    return merged


def public_ai_settings() -> dict[str, Any]:
    ai = load_config().get("ai", {})
    return {
        "api_type": ai.get("api_type", "OpenAI-compatible"),
        "base_url": ai.get("base_url", ""),
        "model": ai.get("model", ""),
        "temperature": ai.get("temperature", 0.2),
        "max_tokens": ai.get("max_tokens", 1800),
        "stream": bool(ai.get("stream", False)),
        "timeout_seconds": ai.get("timeout_seconds", 60),
        "has_api_key": bool(ai.get("api_key")),
    }


def update_ai_settings(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    ai = config.setdefault("ai", {})
    for field in ("api_type", "base_url", "model", "temperature", "max_tokens", "stream", "timeout_seconds"):
        if field in payload and payload[field] is not None:
            ai[field] = payload[field]
    if payload.get("api_key"):
        ai["api_key"] = payload["api_key"]
    config["ai"] = ai
    save_config(config)
    return public_ai_settings()


def public_patenthub_settings() -> dict[str, Any]:
    config = load_config()
    patenthub = config.get("patenthub", {})
    automation = config.get("automation", {})
    return {
        "base_url": patenthub.get("base_url", "https://www.patenthub.cn"),
        "username": patenthub.get("username", ""),
        "has_password": bool(patenthub.get("password")),
        "default_download_limit": int(automation.get("default_download_limit", 100) or 100),
        "max_download_limit": int(automation.get("max_download_limit", 500) or 500),
        "browser_channel": automation.get("browser_channel", "msedge"),
    }


def update_patenthub_settings(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    patenthub = config.setdefault("patenthub", {})
    automation = config.setdefault("automation", {})

    if "base_url" in payload and payload["base_url"]:
        patenthub["base_url"] = str(payload["base_url"]).strip().rstrip("/")
    if "username" in payload:
        patenthub["username"] = str(payload.get("username") or "").strip()
    if payload.get("password"):
        patenthub["password"] = str(payload["password"])

    if "default_download_limit" in payload and payload["default_download_limit"] is not None:
        max_limit = int(automation.get("max_download_limit", 500) or 500)
        automation["default_download_limit"] = max(1, min(int(payload["default_download_limit"]), max_limit))

    config["patenthub"] = patenthub
    config["automation"] = automation
    save_config(config)
    return public_patenthub_settings()


def load_prompts() -> dict[str, str]:
    return read_yaml(CONFIG_DIR / "prompts.yaml", {})


def load_field_mapping_config() -> dict[str, Any]:
    return read_yaml(CONFIG_DIR / "field_mapping.yaml", {"standard_fields": {}})


def load_history() -> list[dict[str, Any]]:
    ensure_data_dirs()
    if not HISTORY_PATH.exists():
        return []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_history(items: list[dict[str, Any]]) -> None:
    ensure_data_dirs()
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_history(entry: dict[str, Any]) -> dict[str, Any]:
    items = load_history()
    entry.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    items.insert(0, entry)
    save_history(items[:100])
    return entry


def delete_history(task_id: str) -> bool:
    items = load_history()
    kept = [item for item in items if item.get("task_id") != task_id]
    if len(kept) == len(items):
        return False
    save_history(kept)
    return True


def upload_meta_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.json"


def output_path(filename: str) -> Path:
    return OUTPUT_DIR / filename
