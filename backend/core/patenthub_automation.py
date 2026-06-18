from __future__ import annotations


class PatentHubAutomation:
    """Reserved interface for a future Playwright-based PatentHub workflow."""

    async def login(self, username: str, password: str) -> None:
        raise NotImplementedError("第一版暂不实现 PatentHub 自动登录。")

    async def search(self, query: str) -> None:
        raise NotImplementedError("第一版暂不实现 PatentHub 自动检索。")


