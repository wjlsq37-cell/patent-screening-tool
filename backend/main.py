from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.analyze_api import router as analyze_router
from backend.api.keyword_api import router as keyword_router
from backend.api.patenthub_api import router as patenthub_router
from backend.api.settings_api import router as settings_router
from backend.api.upload_api import router as upload_router
from backend.core.config_manager import ensure_data_dirs


PROJECT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_DIR / "frontend"

app = FastAPI(title="PatentHub AI 专利分析操作台", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_data_dirs()
app.include_router(settings_router)
app.include_router(keyword_router)
app.include_router(upload_router)
app.include_router(analyze_router)
app.include_router(patenthub_router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
