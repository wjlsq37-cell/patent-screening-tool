from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.analysis_pipeline import analyze_xlsx_file
from backend.core.config_manager import (
    add_history,
    load_config,
    public_patenthub_settings,
    update_patenthub_settings,
)
from backend.core.patenthub_downloader import PatentHubDownloader, PatentHubDownloadOptions
from backend.core.upload_store import get_upload_file_path, preview_upload_file, register_xlsx_file


router = APIRouter(prefix="/api/patenthub", tags=["patenthub"])


class PatentHubSettingsPayload(BaseModel):
    base_url: str = "https://www.patenthub.cn"
    username: str = ""
    password: str | None = None
    default_download_limit: int = Field(default=100, ge=1, le=500)


class AutomationStartPayload(BaseModel):
    requirement: str
    keyword_analysis: dict[str, Any] | None = None
    search_query: str
    download_limit: int = Field(default=100, ge=1, le=500)
    max_ai_summary: int = Field(default=10, ge=0, le=200)
    important_applicants: list[str] = []


@dataclass
class AutomationTask:
    task_id: str
    status: str = "created"
    progress: int = 0
    message: str = "任务已创建。"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    preview: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str = ""
    continue_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    worker: asyncio.Task | None = None

    def update(self, status: str | None = None, progress: int | None = None, message: str | None = None) -> None:
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = max(0, min(int(progress), 100))
        if message is not None:
            self.message = message
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def public(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "preview": self.preview,
            "result": self.result,
            "error": self.error,
            "waiting_for_user": self.status == "waiting_user_verification",
        }


TASKS: dict[str, AutomationTask] = {}


def _payload_dict(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _choose_search_query(payload: AutomationStartPayload) -> str:
    query = (payload.search_query or "").strip()
    if query:
        return query
    keyword_analysis = payload.keyword_analysis or {}
    formulas = keyword_analysis.get("推荐检索式") or []
    if isinstance(formulas, list) and formulas:
        return str(formulas[0]).strip()
    if isinstance(formulas, str) and formulas.strip():
        return formulas.strip()
    return payload.requirement.strip()


@router.get("/settings")
def get_patenthub_settings() -> dict[str, Any]:
    return {"patenthub": public_patenthub_settings()}


@router.post("/settings")
def save_patenthub_settings(payload: PatentHubSettingsPayload) -> dict[str, Any]:
    return {"patenthub": update_patenthub_settings(_payload_dict(payload))}


@router.post("/automation/start")
async def start_automation(payload: AutomationStartPayload) -> dict[str, Any]:
    config = load_config()
    patenthub = config.get("patenthub", {})
    automation = config.get("automation", {})
    username = str(patenthub.get("username") or "").strip()
    password = str(patenthub.get("password") or "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="请先保存 PatentHub 账号和密码。")
    if not payload.requirement.strip():
        raise HTTPException(status_code=400, detail="请先填写专利检索需求。")

    max_limit = int(automation.get("max_download_limit", 500) or 500)
    download_limit = max(1, min(int(payload.download_limit), max_limit))
    search_query = _choose_search_query(payload)
    if not search_query:
        raise HTTPException(status_code=400, detail="请先填写检索式或关键词。")

    task = AutomationTask(task_id=uuid4().hex)
    TASKS[task.task_id] = task
    task.worker = asyncio.create_task(_run_automation(task, payload, config, search_query, download_limit))
    return task.public()


@router.get("/automation/{task_id}/status")
def automation_status(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="未找到自动化任务。")
    return task.public()


@router.post("/automation/{task_id}/continue")
def continue_automation(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="未找到自动化任务。")
    task.continue_event.set()
    task.update(message="已收到继续指令，正在检查登录状态。")
    return task.public()


@router.post("/automation/{task_id}/cancel")
def cancel_automation(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="未找到自动化任务。")
    task.cancel_event.set()
    if task.worker and not task.worker.done():
        task.worker.cancel()
    task.update("cancelled", task.progress, "任务已取消。")
    return task.public()


async def _run_automation(
    task: AutomationTask,
    payload: AutomationStartPayload,
    config: dict[str, Any],
    search_query: str,
    download_limit: int,
) -> None:
    patenthub = config.get("patenthub", {})
    automation_config = config.get("automation", {})

    async def status_callback(status: str, progress: int, message: str) -> None:
        task.update(status, progress, message)

    try:
        downloader = PatentHubDownloader()
        download = await downloader.download_xlsx(
            PatentHubDownloadOptions(
                base_url=str(patenthub.get("base_url") or "https://www.patenthub.cn"),
                browser_channel=str(automation_config.get("browser_channel") or "msedge"),
                headless=bool(automation_config.get("headless", False)),
                username=str(patenthub.get("username") or ""),
                password=str(patenthub.get("password") or ""),
                query=search_query,
                download_limit=download_limit,
            ),
            task.continue_event,
            task.cancel_event,
            status_callback,
        )

        meta = register_xlsx_file(download.file_path, download.original_name, "patenthub_auto")
        task.preview = preview_upload_file(meta["file_id"])
        task.update("analyzing", 88, "xlsx 已读取，正在自动评分、总结并导出 Excel...")

        file_path = get_upload_file_path(meta["file_id"])
        analysis = await analyze_xlsx_file(
            file_path,
            task.preview.get("active_sheet"),
            payload.requirement,
            payload.keyword_analysis or {},
            task.preview.get("field_mapping"),
            payload.max_ai_summary,
            payload.important_applicants,
        )
        add_history(
            {
                "task_id": task.task_id,
                "input_filename": meta.get("original_name") or file_path.name,
                "output_filename": analysis["output_filename"],
                "row_count": analysis["row_count"],
                "requirement": payload.requirement,
                "warnings": analysis["warnings"],
                "source": "patenthub_auto",
            }
        )
        task.result = {
            "task_id": task.task_id,
            "row_count": analysis["row_count"],
            "download_url": f"/api/history/{task.task_id}/download",
            "output_filename": analysis["output_filename"],
            "warnings": analysis["warnings"],
            "top_records": analysis["top_records"],
        }
        task.update("completed", 100, f"自动检索和分析完成，共处理 {analysis['row_count']} 条专利。")
    except asyncio.CancelledError:
        task.update("cancelled", task.progress, "任务已取消。")
    except Exception as exc:
        task.error = str(exc)
        task.update("failed", task.progress, str(exc))
