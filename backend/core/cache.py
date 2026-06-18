from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.config_manager import CACHE_DIR, ensure_data_dirs


class SummaryCache:
    def __init__(self, path: Path | None = None):
        ensure_data_dirs()
        self.path = path or (CACHE_DIR / "summary_cache.json")
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        return self._data

    def get(self, key: str) -> Any | None:
        return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

