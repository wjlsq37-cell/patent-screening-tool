from __future__ import annotations


def classify_legal_status(status: str) -> str:
    text = str(status or "").strip()
    if not text:
        return "法律状态不明"
    if any(word in text for word in ["驳回", "拒绝"]):
        return "驳回_撤回"
    if any(word in text for word in ["撤回", "视为撤回"]):
        return "驳回_撤回"
    if any(word in text for word in ["失效", "终止", "届满", "未缴", "放弃", "期满", "无效"]):
        return "失效_终止_届满"
    if any(word in text for word in ["审中", "实质审查", "实审", "等待实审", "进入审查"]):
        return "审中_实质审查"
    if any(word in text for word in ["授权", "有效", "专利权维持", "专利权有效"]):
        return "有效_授权专利"
    if any(word in text for word in ["公开", "公布"]):
        return "审中_实质审查"
    return "法律状态不明"


def legal_status_score(status: str) -> float:
    category = classify_legal_status(status)
    if category == "有效_授权专利":
        return 95.0
    if category == "审中_实质审查":
        return 75.0
    if category == "失效_终止_届满":
        return 35.0
    if category == "驳回_撤回":
        return 25.0
    return 45.0

