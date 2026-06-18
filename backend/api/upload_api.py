from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.core.config_manager import ensure_data_dirs
from backend.core.upload_store import preview_upload_file, register_xlsx_file


router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/uploads")
async def upload_xlsx(file: UploadFile = File(...)) -> dict:
    ensure_data_dirs()
    original_name = file.filename or "upload.xlsx"
    suffix = Path(original_name).suffix.lower()
    if suffix != ".xlsx":
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件。")

    temp_path = None
    try:
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp:
            temp_path = Path(temp.name)
            while chunk := await file.read(1024 * 1024):
                temp.write(chunk)
        meta = register_xlsx_file(temp_path, original_name, "manual_upload")
        return preview_upload_file(meta["file_id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"xlsx 读取失败：{exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@router.get("/uploads/{file_id}/preview")
def preview_upload(file_id: str, sheet_name: str | None = Query(default=None)) -> dict:
    try:
        return preview_upload_file(file_id, sheet_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"xlsx 预览失败：{exc}") from exc
