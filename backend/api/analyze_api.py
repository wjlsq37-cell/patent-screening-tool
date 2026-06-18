from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.upload_api import get_upload_file_path
from backend.core.config_manager import add_history, delete_history, load_config, load_history, output_path
from backend.core.excel_exporter import export_analysis
from backend.core.excel_reader import read_sheet, standardize_records
from backend.core.field_mapper import STANDARD_FIELDS, auto_map_fields, validate_mapping
from backend.core.patent_ranker import rank_patents
from backend.core.patent_summarizer import summarize_records


router = APIRouter(prefix="/api", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    requirement: str = ""
    keyword_analysis: dict[str, Any] | None = None
    field_mapping: dict[str, str] | None = None
    max_ai_summary: int = Field(default=10, ge=0, le=200)
    important_applicants: list[str] = []


def _mapping_warnings(mapping: dict[str, str]) -> list[str]:
    warnings = []
    recommended = ["专利名称", "申请号", "公开号", "申请人", "摘要", "法律状态"]
    missing = [field for field in recommended if not mapping.get(field)]
    if missing:
        warnings.append(f"以下推荐字段未映射：{'、'.join(missing)}。结果仍会生成，但建议人工复核。")
    return warnings


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
    if not payload.requirement.strip():
        raise HTTPException(status_code=400, detail="请先填写专利检索需求。")

    file_path = get_upload_file_path(payload.file_id)
    try:
        df = read_sheet(file_path, payload.sheet_name)
        columns = [str(col) for col in df.columns]
        mapping = validate_mapping(payload.field_mapping or auto_map_fields(columns), columns)
        records = standardize_records(df, mapping)
        if not records:
            raise ValueError("未读取到专利记录。")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败：{exc}") from exc

    config = load_config()
    warnings = _mapping_warnings(mapping)
    try:
        ranked = rank_patents(
            records,
            payload.requirement,
            payload.keyword_analysis or {},
            config,
            payload.important_applicants,
        )
        summarized, summary_warnings = await summarize_records(
            ranked,
            payload.requirement,
            payload.keyword_analysis or {},
            payload.max_ai_summary,
        )
        warnings.extend(summary_warnings)
        output_file, output_filename = export_analysis(
            summarized,
            payload.requirement,
            payload.keyword_analysis or {},
            warnings,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析或导出失败：{exc}") from exc

    task_id = uuid4().hex
    add_history(
        {
            "task_id": task_id,
            "input_filename": file_path.name,
            "output_filename": output_filename,
            "row_count": len(ranked),
            "requirement": payload.requirement,
            "warnings": warnings,
        }
    )
    return {
        "task_id": task_id,
        "row_count": len(ranked),
        "download_url": f"/api/history/{task_id}/download",
        "output_filename": output_filename,
        "warnings": warnings,
        "top_records": summarized[:10],
    }


@router.get("/history")
def history() -> dict[str, Any]:
    return {"items": load_history()}


@router.get("/history/{task_id}/download")
def download(task_id: str) -> FileResponse:
    entry = next((item for item in load_history() if item.get("task_id") == task_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="未找到历史任务。")
    path = output_path(entry["output_filename"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件已不存在。")
    return FileResponse(path, filename=entry["output_filename"])


@router.delete("/history/{task_id}")
def remove_history(task_id: str) -> dict[str, Any]:
    entry = next((item for item in load_history() if item.get("task_id") == task_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="未找到历史任务。")
    path = output_path(entry.get("output_filename", ""))
    if path.exists():
        path.unlink()
    deleted = delete_history(task_id)
    return {"ok": deleted}

