from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.config_manager import public_ai_settings, update_ai_settings
from backend.core.llm_client import LLMClient, LLMError


router = APIRouter(prefix="/api", tags=["settings"])


class AISettingsPayload(BaseModel):
    api_type: str = "OpenAI-compatible"
    base_url: str = ""
    api_key: str | None = None
    model: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1800, ge=1, le=32000)
    stream: bool = False
    timeout_seconds: int = Field(default=60, ge=5, le=300)


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return {"ai": public_ai_settings()}


@router.post("/settings")
def save_settings(payload: AISettingsPayload) -> dict[str, Any]:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {"ai": update_ai_settings(data)}


@router.post("/settings/test")
async def test_settings() -> dict[str, Any]:
    try:
        return await LLMClient().test_connection()
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
