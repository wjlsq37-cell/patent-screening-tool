from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.core.analysis_pipeline import analyze_xlsx_file
from backend.core.config_manager import add_history, delete_history, load_history, output_path
from backend.core.upload_store import get_upload_file_path


router = APIRouter(prefix="/api", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    requirement: str = ""
    keyword_analysis: dict[str, Any] | None = None
    field_mapping: dict[str, str] | None = None
    max_ai_summary: int = Field(default=10, ge=0, le=200)
    important_applicants: list[str] = []


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
    if not payload.requirement.strip():
        raise HTTPException(status_code=400, detail="请先填写专利检索需求。")

    try:
        file_path = get_upload_file_path(payload.file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        result = await analyze_xlsx_file(
            file_path,
            payload.sheet_name,
            payload.requirement,
            payload.keyword_analysis or {},
            payload.field_mapping,
            payload.max_ai_summary,
            payload.important_applicants,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"读取上传文件失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析或导出失败：{exc}") from exc

    task_id = uuid4().hex
    add_history(
        {
            "task_id": task_id,
            "input_filename": file_path.name,
            "output_filename": result["output_filename"],
            "row_count": result["row_count"],
            "requirement": payload.requirement,
            "warnings": result["warnings"],
        }
    )
    return {
        "task_id": task_id,
        "row_count": result["row_count"],
        "download_url": f"/api/history/{task_id}/download",
        "output_filename": result["output_filename"],
        "warnings": result["warnings"],
        "top_records": result["top_records"],
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
