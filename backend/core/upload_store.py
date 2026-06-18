from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from backend.core.config_manager import UPLOAD_DIR, ensure_data_dirs, upload_meta_path
from backend.core.excel_reader import list_sheets, preview_dataframe, read_sheet


def save_upload_meta(file_id: str, meta: dict) -> None:
    path = upload_meta_path(file_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_upload_meta(file_id: str) -> dict:
    path = upload_meta_path(file_id)
    if not path.exists():
        raise FileNotFoundError("未找到上传文件，请重新上传。")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_upload_file_path(file_id: str) -> Path:
    meta = load_upload_meta(file_id)
    path = Path(meta["saved_path"])
    if not path.exists():
        raise FileNotFoundError("上传文件已不存在，请重新上传。")
    return path


def register_xlsx_file(source_path: Path, original_name: str | None = None, source: str = "manual_upload") -> dict:
    ensure_data_dirs()
    if source_path.suffix.lower() != ".xlsx":
        raise ValueError("请提供 .xlsx 文件。")

    file_id = uuid4().hex
    saved_path = UPLOAD_DIR / f"{file_id}.xlsx"
    shutil.copy2(source_path, saved_path)
    meta = {
        "file_id": file_id,
        "original_name": original_name or source_path.name,
        "saved_path": str(saved_path),
        "source": source,
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_upload_meta(file_id, meta)
    return meta


def preview_upload_file(file_id: str, sheet_name: str | None = None) -> dict:
    meta = load_upload_meta(file_id)
    path = get_upload_file_path(file_id)
    sheets = list_sheets(path)
    active_sheet = sheet_name if sheet_name in sheets else sheets[0]
    df = read_sheet(path, active_sheet)
    preview = preview_dataframe(df)
    return {
        "file_id": file_id,
        "filename": meta.get("original_name", path.name),
        "sheets": sheets,
        "active_sheet": active_sheet,
        **preview,
    }

