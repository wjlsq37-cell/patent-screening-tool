from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.core.patenthub_automation import PatentHubAutomation, PatentHubDownloadResult


@dataclass
class PatentHubDownloadOptions:
    base_url: str
    browser_channel: str
    headless: bool
    username: str
    password: str
    query: str
    download_limit: int


class PatentHubDownloader:
    async def download_xlsx(
        self,
        options: PatentHubDownloadOptions,
        continue_event: asyncio.Event,
        cancel_event: asyncio.Event,
        status_callback,
    ) -> PatentHubDownloadResult:
        automation = PatentHubAutomation(options.base_url, options.browser_channel, options.headless)
        try:
            return await automation.download_xlsx(
                options.query,
                options.download_limit,
                options.username,
                options.password,
                continue_event,
                cancel_event,
                status_callback,
            )
        finally:
            await automation.close()
