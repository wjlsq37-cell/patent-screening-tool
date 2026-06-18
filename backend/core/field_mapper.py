from __future__ import annotations

import re
from typing import Any

from backend.core.config_manager import load_field_mapping_config


STANDARD_FIELDS = [
    "专利名称",
    "申请号",
    "公开号",
    "申请日",
    "公开日",
    "授权日",
    "申请人",
    "发明人",
    "摘要",
    "权利要求",
    "法律状态",
    "专利类型",
    "IPC 分类号",
    "详情链接",
]


def _normalize(text: Any) -> str:
    text = str(text or "").strip().lower()
    return re.sub(r"[\s_\-（）()【】\[\]{}:：/\\]+", "", text)


def auto_map_fields(columns: list[str]) -> dict[str, str]:
    config = load_field_mapping_config()
    field_defs = config.get("standard_fields", {})
    normalized_columns = {_normalize(col): col for col in columns}
    mapping: dict[str, str] = {}

    for field in STANDARD_FIELDS:
        aliases = [field]
        aliases.extend(field_defs.get(field, {}).get("aliases", []))
        selected = ""

        for alias in aliases:
            normalized_alias = _normalize(alias)
            if normalized_alias in normalized_columns:
                selected = normalized_columns[normalized_alias]
                break

        if not selected:
            for col in columns:
                normalized_col = _normalize(col)
                if any(_normalize(alias) and _normalize(alias) in normalized_col for alias in aliases):
                    selected = col
                    break

        mapping[field] = selected
    return mapping


def validate_mapping(mapping: dict[str, str], columns: list[str]) -> dict[str, str]:
    valid = {}
    available = set(columns)
    for field in STANDARD_FIELDS:
        source = mapping.get(field, "")
        valid[field] = source if source in available else ""
    return valid

