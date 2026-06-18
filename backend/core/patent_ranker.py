from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from backend.core.legal_status_classifier import classify_legal_status, legal_status_score


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flatten_keywords(keyword_analysis: dict[str, Any] | None, requirement: str) -> tuple[list[str], list[str]]:
    keyword_analysis = keyword_analysis or {}
    core_keys = ["核心关键词", "core_keywords", "coreKeywords"]
    expanded_keys = ["扩展关键词", "同义词", "expanded_keywords", "synonyms"]
    core: list[str] = []
    expanded: list[str] = []

    def add_values(target: list[str], value: Any) -> None:
        if isinstance(value, str):
            parts = re.split(r"[,，;；、\n\s]+", value)
        elif isinstance(value, list):
            parts = value
        else:
            parts = []
        for part in parts:
            text = _as_text(part)
            if len(text) >= 2 and text not in target:
                target.append(text)

    for key in core_keys:
        add_values(core, keyword_analysis.get(key))
    for key in expanded_keys:
        add_values(expanded, keyword_analysis.get(key))

    if not core:
        for token in re.split(r"[,，;；。、“”\"'\n\s]+", requirement or ""):
            token = token.strip()
            if len(token) >= 2:
                core.append(token[:24])
    return core[:30], expanded[:50]


def _parse_date(value: Any) -> date | None:
    text = _as_text(value)
    if not text:
        return None
    try:
        parsed = pd.to_datetime(text, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    haystack = _as_text(text).lower()
    hits = []
    for keyword in keywords:
        kw = keyword.lower().strip()
        if len(kw) >= 2 and kw in haystack and keyword not in hits:
            hits.append(keyword)
    return hits


def relevance_score(record: dict[str, Any], requirement: str, keyword_analysis: dict[str, Any] | None) -> tuple[float, list[str]]:
    core, expanded = _flatten_keywords(keyword_analysis, requirement)
    title = record.get("专利名称", "")
    abstract = record.get("摘要", "")
    claims = record.get("权利要求", "")
    ipc = record.get("IPC 分类号", "")

    title_hits = _keyword_hits(title, core)
    abstract_hits = _keyword_hits(abstract, core + expanded)
    claim_hits = _keyword_hits(claims, core + expanded)
    ipc_hits = _keyword_hits(ipc, core + expanded)

    score = 0.0
    score += min(len(title_hits) * 14, 38)
    score += min(len(abstract_hits) * 8, 28)
    score += min(len(claim_hits) * 9, 24)
    score += min(len(ipc_hits) * 3, 6)

    combined = f"{title} {abstract} {claims}"
    broad_terms = [kw for kw in core[:8] if kw in combined]
    score += min(len(broad_terms) * 2, 8)

    hits = []
    for hit in title_hits + abstract_hits + claim_hits + ipc_hits:
        if hit not in hits:
            hits.append(hit)
    return min(score, 100.0), hits


def applicant_score(applicant: str, important_applicants: list[str], config: dict[str, Any]) -> tuple[float, bool]:
    applicant = _as_text(applicant)
    if not applicant:
        return 25.0, False

    important = [item.strip() for item in important_applicants if item and item.strip()]
    is_important = any(name and name in applicant for name in important)
    if is_important:
        return 100.0, True

    analysis_config = config.get("analysis", {})
    company_words = analysis_config.get("company_keywords", [])
    research_words = analysis_config.get("research_keywords", [])
    if any(word and str(word).lower() in applicant.lower() for word in company_words):
        return 80.0, False
    if any(word and str(word).lower() in applicant.lower() for word in research_words):
        return 65.0, False
    if len(applicant) <= 5 and not any(ch in applicant for ch in [";", "；", ",", "，"]):
        return 45.0, False
    return 58.0, False


def time_score(application_date: Any) -> float:
    parsed = _parse_date(application_date)
    if not parsed:
        return 35.0
    years = (date.today() - parsed).days / 365.25
    if years <= 5:
        return 95.0
    if years <= 10:
        return 68.0
    return 38.0


def completeness_score(record: dict[str, Any]) -> float:
    required = ["专利名称", "申请号", "公开号", "申请人", "摘要", "法律状态", "申请日"]
    filled = sum(1 for field in required if _as_text(record.get(field)))
    return round(filled / len(required) * 100, 1)


def remaining_protection(record: dict[str, Any]) -> str:
    app_date = _parse_date(record.get("申请日"))
    if not app_date:
        return "无法估算"
    patent_type = _as_text(record.get("专利类型"))
    years = 20
    if "实用" in patent_type or "外观" in patent_type:
        years = 10
    end_year = app_date.year + years
    try:
        expiry = app_date.replace(year=end_year)
    except ValueError:
        expiry = app_date.replace(year=end_year, day=28)
    days_left = (expiry - date.today()).days
    if days_left <= 0:
        return "可能已届满"
    return f"约{days_left // 365}年"


def recommendation(overall: float) -> str:
    if overall >= 80:
        return "重点阅读"
    if overall >= 55:
        return "一般参考"
    return "可忽略"


def rank_patents(
    records: list[dict[str, Any]],
    requirement: str,
    keyword_analysis: dict[str, Any] | None,
    config: dict[str, Any],
    request_important_applicants: list[str] | None = None,
) -> list[dict[str, Any]]:
    weights = config.get("analysis", {}).get("weights", {})
    config_important = config.get("analysis", {}).get("important_applicants", [])
    important_applicants = list(dict.fromkeys((config_important or []) + (request_important_applicants or [])))

    enriched = []
    for record in records:
        relevance, hits = relevance_score(record, requirement, keyword_analysis)
        legal = legal_status_score(record.get("法律状态", ""))
        applicant, important = applicant_score(record.get("申请人", ""), important_applicants, config)
        time = time_score(record.get("申请日", ""))
        completeness = completeness_score(record)

        overall = (
            relevance * float(weights.get("relevance", 0.50))
            + legal * float(weights.get("legal_status", 0.20))
            + applicant * float(weights.get("applicant", 0.15))
            + time * float(weights.get("time", 0.10))
            + completeness * float(weights.get("completeness", 0.05))
        )
        item = dict(record)
        item.update(
            {
                "综合评分": round(overall, 1),
                "相关度评分": round(relevance, 1),
                "法律状态评分": round(legal, 1),
                "申请人评分": round(applicant, 1),
                "时间评分": round(time, 1),
                "数据完整度评分": round(completeness, 1),
                "推荐等级": recommendation(overall),
                "剩余保护期估算": remaining_protection(record),
                "命中关键词": "、".join(hits),
                "法律状态分类": classify_legal_status(record.get("法律状态", "")),
                "是否重点申请人": important,
            }
        )
        enriched.append(item)

    enriched.sort(key=lambda item: item.get("综合评分", 0), reverse=True)
    for index, item in enumerate(enriched, start=1):
        item["排名"] = index
    return enriched

