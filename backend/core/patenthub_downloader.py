from __future__ import annotations


class PatentHubDownloader:
    """Reserved interface for future PatentHub xlsx download automation."""

    async def download_xlsx(self, query: str) -> str:
        raise NotImplementedError("第一版暂不实现 PatentHub 自动下载。")

