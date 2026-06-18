from __future__ import annotations

from typing import Any

import httpx

from backend.core.config_manager import load_config


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or load_config()
        self.ai = self.config.get("ai", {})

    @property
    def has_api_key(self) -> bool:
        return bool(self.ai.get("api_key"))

    def _chat_url(self) -> str:
        base_url = str(self.ai.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise LLMError("请先配置 Base URL。")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        if not self.has_api_key:
            raise LLMError("请先在 AI 设置中配置 API Key。")

        payload: dict[str, Any] = {
            "model": self.ai.get("model"),
            "messages": messages,
            "temperature": temperature if temperature is not None else self.ai.get("temperature", 0.2),
            "max_tokens": max_tokens if max_tokens is not None else self.ai.get("max_tokens", 1800),
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.ai.get('api_key')}",
            "Content-Type": "application/json",
        }
        timeout = float(self.ai.get("timeout_seconds") or 60)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self._chat_url(), headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:400]
            raise LLMError(f"AI 接口返回错误：HTTP {status}，{detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"AI 接口连接失败：{exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("AI 返回格式异常，未找到 choices[0].message.content。") from exc

    async def test_connection(self) -> dict[str, Any]:
        content = await self.chat(
            [
                {"role": "system", "content": "你是连接测试助手。"},
                {"role": "user", "content": "请只回复：连接成功"},
            ],
            temperature=0,
            max_tokens=30,
        )
        return {"ok": True, "message": content.strip() or "连接成功"}

