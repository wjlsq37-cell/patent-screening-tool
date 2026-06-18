from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from backend.core.cache import SummaryCache
from backend.core.config_manager import load_prompts
from backend.core.llm_client import LLMClient


SUMMARY_FIELDS = [
    "AI 简述",
    "解决的问题",
    "实现方式",
    "核心发明点",
    "与用户需求的关系",
    "可能规避方向",
    "阅读建议",
]


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _cache_key(record: dict[str, Any]) -> str:
    stable = _as_text(record.get("申请号")) or _as_text(record.get("公开号"))
    if not stable:
        stable = "|".join(_as_text(record.get(field)) for field in ["专利名称", "申请人", "摘要"])
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _fallback_summary(record: dict[str, Any], reason: str = "") -> dict[str, str]:
    title = _as_text(record.get("专利名称")) or "未命名专利"
    abstract = _as_text(record.get("摘要"))
    claims = _as_text(record.get("权利要求"))
    notes = []
    if not abstract:
        notes.append("缺少摘要，需人工复核")
    if not claims:
        notes.append("缺少权利要求，需人工复核")
    if reason:
        notes.append(reason)

    brief_source = abstract or title
    if len(brief_source) > 120:
        brief_source = brief_source[:120] + "..."
    review_note = record.get("推荐等级") or "一般参考"
    if review_note not in {"重点阅读", "一般参考", "可忽略"}:
        review_note = "一般参考"

    suffix = f"（{'；'.join(notes)}）" if notes else ""
    return {
        "AI 简述": f"{title}：{brief_source}{suffix}",
        "解决的问题": abstract[:120] if abstract else "缺少摘要，需人工复核",
        "实现方式": claims[:120] if claims else "缺少权利要求，需人工复核",
        "核心发明点": record.get("命中关键词") or "需人工复核",
        "与用户需求的关系": f"综合评分 {record.get('综合评分', '')}，命中关键词：{record.get('命中关键词') or '无明显命中'}",
        "可能规避方向": "需结合权利要求和产品方案人工判断",
        "阅读建议": review_note,
    }


def _normalize_summary(data: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    result = {}
    for field in SUMMARY_FIELDS:
        result[field] = _as_text(data.get(field))
    if result["阅读建议"] not in {"重点阅读", "一般参考", "可忽略"}:
        result["阅读建议"] = record.get("推荐等级") or "一般参考"
    for field, value in _fallback_summary(record).items():
        if not result.get(field):
            result[field] = value
    return result


async def summarize_records(
    records: list[dict[str, Any]],
    requirement: str,
    keyword_analysis: dict[str, Any] | None,
    max_count: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    cache = SummaryCache()
    client = LLMClient()
    prompts = load_prompts()
    prompt = prompts.get("single_patent_summary", "")
    warnings: list[str] = []
    max_count = max(0, int(max_count or 0))

    for index, record in enumerate(records):
        if index >= max_count:
            record.update(
                {
                    "AI 简述": "未纳入 AI 总结范围，可在分析设置中增加总结数量。",
                    "解决的问题": "",
                    "实现方式": "",
                    "核心发明点": "",
                    "与用户需求的关系": "",
                    "可能规避方向": "",
                    "阅读建议": record.get("推荐等级", "一般参考"),
                }
            )
            continue

        key = _cache_key(record)
        cached = cache.get(key)
        if cached:
            record.update(cached)
            continue

        if not client.has_api_key:
            summary = _fallback_summary(record, "未配置 API Key，已使用本地摘要")
            record.update(summary)
            warning = "未配置 API Key，前 N 篇专利使用本地摘要占位。"
            if warning not in warnings:
                warnings.append(warning)
            continue

        payload = {
            "用户需求": requirement,
            "关键词分析": keyword_analysis or {},
            "专利字段": {
                field: record.get(field, "")
                for field in [
                    "专利名称",
                    "申请号",
                    "公开号",
                    "申请人",
                    "发明人",
                    "摘要",
                    "权利要求",
                    "法律状态",
                    "专利类型",
                    "IPC 分类号",
                    "命中关键词",
                    "综合评分",
                ]
            },
        }
        try:
            content = await client.chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                json_mode=True,
            )
            summary = _normalize_summary(_extract_json(content), record)
        except Exception as exc:
            summary = _fallback_summary(record, f"AI 总结失败：{exc}")
            warnings.append(f"{record.get('专利名称') or record.get('申请号') or '专利'}：AI 总结失败，已使用本地摘要。")
            record.update(summary)
            continue
        record.update(summary)
        cache.set(key, summary)

    return records, warnings
