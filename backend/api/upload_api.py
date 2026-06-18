from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.core.config_manager import UPLOAD_DIR, ensure_data_dirs, upload_meta_path
from backend.core.excel_reader import list_sheets, preview_dataframe, read_sheet


router = APIRouter(prefix="/api", tags=["upload"])


def _save_meta(file_id: str, meta: dict) -> None:
    path = upload_meta_path(file_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _load_meta(file_id: str) -> dict:
    path = upload_meta_path(file_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="未找到上传文件，请重新上传。")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_upload_file_path(file_id: str) -> Path:
    meta = _load_meta(file_id)
    path = Path(meta["saved_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="上传文件已不存在，请重新上传。")
    return path


def _preview_response(file_id: str, path: Path, sheet_name: str | None = None) -> dict:
    sheets = list_sheets(path)
    active_sheet = sheet_name if sheet_name in sheets else sheets[0]
    df = read_sheet(path, active_sheet)
    preview = preview_dataframe(df)
    return {
        "file_id": file_id,
        "sheets": sheets,
        "active_sheet": active_sheet,
        **preview,
    }


@router.post("/uploads")
async def upload_xlsx(file: UploadFile = File(...)) -> dict:
    ensure_data_dirs()
    original_name = file.filename or "upload.xlsx"
    suffix = Path(original_name).suffix.lower()
    if suffix != ".xlsx":
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件。")

    file_id = uuid4().hex
    saved_path = UPLOAD_DIR / f"{file_id}.xlsx"
    try:
        with saved_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        meta = {
            "file_id": file_id,
            "original_name": original_name,
            "saved_path": str(saved_path),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save_meta(file_id, meta)
        response = _preview_response(file_id, saved_path)
        response["filename"] = original_name
        return response
    except Exception as exc:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=400, detail=f"xlsx 读取失败：{exc}") from exc


@router.get("/uploads/{file_id}/preview")
def preview_upload(file_id: str, sheet_name: str | None = Query(default=None)) -> dict:
    path = get_upload_file_path(file_id)
    try:
        return _preview_response(file_id, path, sheet_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"xlsx 预览失败：{exc}") from exc

