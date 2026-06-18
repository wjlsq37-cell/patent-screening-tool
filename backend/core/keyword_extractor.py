from __future__ import annotations

import json
import re
from typing import Any

from backend.core.config_manager import load_prompts
from backend.core.llm_client import LLMClient, LLMError


KEYWORD_FIELDS = [
    "核心关键词",
    "扩展关键词",
    "同义词",
    "排除词",
    "推荐检索式",
    "推荐检索字段",
    "检索注意事项",
]


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("AI 未返回内容。")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _normalize_result(data: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for field in KEYWORD_FIELDS:
        value = data.get(field, [])
        if isinstance(value, str):
            values = [item.strip() for item in re.split(r"[\n;；]+", value) if item.strip()]
        elif isinstance(value, list):
            values = [str(item).strip() for item in value if str(item).strip()]
        else:
            values = []
        result[field] = values
    return result


async def extract_keywords(requirement: str) -> dict[str, list[str]]:
    if not requirement.strip():
        raise ValueError("请输入专利检索需求。")

    prompts = load_prompts()
    system_prompt = prompts.get("keyword_extract", "")
    client = LLMClient()
    try:
        content = await client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": requirement.strip()},
            ],
            json_mode=True,
        )
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"关键词拆解失败：{exc}") from exc

    try:
        return _normalize_result(_extract_json(content))
    except Exception as exc:
        raise LLMError(f"AI 返回格式异常，无法解析关键词 JSON：{exc}") from exc

