from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.keyword_extractor import extract_keywords
from backend.core.llm_client import LLMError


router = APIRouter(prefix="/api", tags=["keywords"])


class KeywordRequest(BaseModel):
    requirement: str


@router.post("/keywords/extract")
async def extract(payload: KeywordRequest) -> dict[str, Any]:
    try:
        result = await extract_keywords(payload.requirement)
        return {"result": result}
    except (ValueError, LLMError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

