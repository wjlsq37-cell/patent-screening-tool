from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import quote
from uuid import uuid4

from backend.core.config_manager import UPLOAD_DIR, ensure_data_dirs


StatusCallback = Callable[[str, int, str], Awaitable[None]]


class PatentHubAutomationError(RuntimeError):
    pass


@dataclass
class PatentHubDownloadResult:
    file_path: Path
    original_name: str


class PatentHubAutomation:
    def __init__(self, base_url: str, browser_channel: str = "msedge", headless: bool = False):
        self.base_url = base_url.rstrip("/")
        self.browser_channel = browser_channel or "msedge"
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def close(self) -> None:
        for obj in (self._context, self._browser):
            if obj:
                try:
                    await obj.close()
                except Exception:
                    pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

    async def download_xlsx(
        self,
        query: str,
        download_limit: int,
        username: str,
        password: str,
        continue_event: asyncio.Event,
        cancel_event: asyncio.Event,
        status_callback: StatusCallback,
    ) -> PatentHubDownloadResult:
        if not username or not password:
            raise PatentHubAutomationError("请先保存 PatentHub 账号和密码。")
        if not query.strip():
            raise PatentHubAutomationError("请先填写检索式或关键词。")

        await self._notify(status_callback, "running", 5, "正在启动系统 Edge 浏览器...")
        page = await self._open_browser()

        await self._check_cancel(cancel_event)
        search_url = f"{self.base_url}/s?q={quote(query.strip())}"
        await self._notify(status_callback, "running", 15, "正在打开 PatentHub 搜索页...")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        if self._is_login_url(page.url):
            await self._login(page, username, password, continue_event, cancel_event, status_callback)
            await self._notify(status_callback, "running", 40, "登录完成，正在回到搜索结果页...")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

        await self._check_cancel(cancel_event)
        if self._is_login_url(page.url):
            raise PatentHubAutomationError("仍停留在登录页，请确认账号密码或手动完成验证后重试。")

        selected = await self._select_first_results(page, 1)
        if selected <= 0:
            await self._notify(status_callback, "downloading", 62, "未识别到结果选择框，将尝试使用下载著录项的范围下载。")

        await self._notify(status_callback, "downloading", 70, f"正在打开下载著录项，并设置下载范围 1-{download_limit}...")
        download_path = await self._trigger_xlsx_download(page, download_limit, status_callback)
        await self._notify(status_callback, "downloading", 85, "xlsx 已下载，正在交给分析流程...")
        return PatentHubDownloadResult(download_path, download_path.name)

    async def _open_browser(self):
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise PatentHubAutomationError("缺少 Playwright 依赖，请重新安装依赖或重新打包便携版。") from exc

        ensure_data_dirs()
        downloads_path = UPLOAD_DIR / "_patenthub_downloads"
        downloads_path.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch(
                channel=self.browser_channel,
                headless=self.headless,
                downloads_path=str(downloads_path),
            )
        except Exception as exc:
            raise PatentHubAutomationError(
                "无法启动系统 Microsoft Edge。请确认电脑已安装/启用 Edge，或改用手动上传 xlsx。"
            ) from exc

        self._context = await self._browser.new_context(accept_downloads=True)
        self._page = await self._context.new_page()
        return self._page

    async def _login(
        self,
        page,
        username: str,
        password: str,
        continue_event: asyncio.Event,
        cancel_event: asyncio.Event,
        status_callback: StatusCallback,
    ) -> None:
        await self._notify(status_callback, "running", 22, "正在填写 PatentHub 登录信息...")
        await self._fill_login_form(page, username, password)
        await self._click_login_button(page)
        await page.wait_for_timeout(4000)

        if not self._is_login_url(page.url):
            return

        await self._notify(
            status_callback,
            "waiting_user_verification",
            30,
            "请在打开的 Edge 浏览器中手动完成验证码、滑块或二次验证，然后点击本页面“我已完成验证，继续”。",
        )
        await self._wait_continue_or_cancel(continue_event, cancel_event)
        await page.wait_for_timeout(2000)
        if self._is_login_url(page.url):
            await self._click_login_button(page)
            await page.wait_for_timeout(3000)
        if self._is_login_url(page.url):
            raise PatentHubAutomationError("登录仍未完成，请检查账号密码或验证码状态。")

    async def _fill_login_form(self, page, username: str, password: str) -> None:
        inputs = page.locator("input:visible")
        count = await inputs.count()
        if count < 2:
            raise PatentHubAutomationError("未识别到 PatentHub 登录输入框。")

        await inputs.nth(0).fill(username, timeout=10000)
        password_inputs = page.locator("input[type='password']:visible")
        if await password_inputs.count():
            await password_inputs.nth(0).fill(password, timeout=10000)
        else:
            await inputs.nth(1).fill(password, timeout=10000)

    async def _click_login_button(self, page) -> None:
        button = page.get_by_role("button", name="登录")
        if await button.count():
            await button.first.click(timeout=10000)
            return
        text_button = page.get_by_text("登录", exact=True)
        if await text_button.count():
            await text_button.first.click(timeout=10000)
            return
        raise PatentHubAutomationError("未识别到 PatentHub 登录按钮。")

    async def _select_first_results(self, page, download_limit: int) -> int:
        await page.wait_for_timeout(3000)
        checkboxes = page.locator("input[type='checkbox']:visible")
        count = await checkboxes.count()
        selected = 0
        for index in range(count):
            if selected >= download_limit:
                break
            checkbox = checkboxes.nth(index)
            try:
                if await self._looks_like_select_all(checkbox):
                    continue
                if await checkbox.is_checked():
                    continue
                await checkbox.check(timeout=1500)
                selected += 1
            except Exception:
                continue
        return selected

    @staticmethod
    async def _looks_like_select_all(checkbox) -> bool:
        try:
            return bool(
                await checkbox.evaluate(
                    """el => {
                        const label = el.closest('label');
                        const text = [
                            label ? label.innerText : '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('title') || '',
                            el.getAttribute('name') || '',
                            el.getAttribute('id') || ''
                        ].join(' ');
                        return Boolean(el.closest('th')) || /全选|select\\s*all/i.test(text);
                    }"""
                )
            )
        except Exception:
            return False

    async def _trigger_xlsx_download(self, page, download_limit: int, status_callback: StatusCallback) -> Path:
        await self._open_bibliography_download_dialog(page)
        await self._notify(status_callback, "downloading", 74, "已打开下载著录项，正在选择范围、xls 格式和 wjl01 模板...")
        await self._configure_bibliography_download_dialog(page, download_limit)

        can_click = await self._has_dialog_download_button(page)
        if not can_click:
            raise PatentHubAutomationError("未能在“下载著录项”弹窗内找到绿色“下载”按钮。")

        async with page.expect_download(timeout=120000) as download_info:
            clicked = await self._click_dialog_download_button(page)
            if not clicked:
                raise PatentHubAutomationError("未能点击“下载著录项”弹窗内的下载按钮。")

        download = await download_info.value
        suggested = download.suggested_filename or "patenthub_download.xlsx"
        if not suggested.lower().endswith(".xlsx"):
            raise PatentHubAutomationError(f"下载文件不是 xlsx：{suggested}")

        safe_name = re.sub(r'[<>:"/\\|?*]+', "_", suggested)
        target = UPLOAD_DIR / "_patenthub_downloads" / f"patenthub_auto_{uuid4().hex[:8]}_{safe_name}"
        await download.save_as(str(target))
        return target

    async def _open_bibliography_download_dialog(self, page) -> None:
        if await self._has_bibliography_download_dialog(page):
            return

        selectors = [
            "[title*='下载著录项']",
            "[aria-label*='下载著录项']",
            "[data-original-title*='下载著录项']",
            "[data-bs-title*='下载著录项']",
            "[data-title*='下载著录项']",
        ]
        for selector in selectors:
            locators = page.locator(selector)
            count = min(await locators.count(), 10)
            for index in range(count):
                locator = locators.nth(index)
                try:
                    if not await locator.is_visible(timeout=1000):
                        continue
                    await locator.click(timeout=5000)
                    if await self._wait_for_bibliography_download_dialog(page):
                        return
                except Exception:
                    continue

        clicked = await page.evaluate(
            """() => {
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const labels = ['下载著录项'];
                const elements = Array.from(document.querySelectorAll('button,a,[role="button"],i,span,div'));
                for (const el of elements) {
                    if (!visible(el)) continue;
                    const text = [
                        el.innerText || '',
                        el.getAttribute('title') || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('data-original-title') || '',
                        el.getAttribute('data-bs-title') || '',
                        el.getAttribute('data-title') || ''
                    ].join(' ');
                    if (labels.some((label) => text.includes(label))) {
                        el.scrollIntoView({ block: 'center', inline: 'center' });
                        el.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
        if clicked and await self._wait_for_bibliography_download_dialog(page):
            return

        raise PatentHubAutomationError("未能找到“下载著录项”按钮，请确认 PatentHub 页面已进入检索结果页。")

    async def _wait_for_bibliography_download_dialog(self, page) -> bool:
        for _ in range(20):
            if await self._has_bibliography_download_dialog(page):
                return True
            await page.wait_for_timeout(500)
        return False

    async def _has_bibliography_download_dialog(self, page) -> bool:
        return bool(
            await page.evaluate(
                """() => {
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden'
                            && style.display !== 'none'
                            && rect.width > 0
                            && rect.height > 0;
                    };
                    const dialogs = Array.from(document.querySelectorAll('div,section,article,[role="dialog"]'))
                        .filter(visible)
                        .filter((el) => {
                            const text = el.innerText || '';
                            return text.includes('下载著录项') && text.includes('导出范围');
                        });
                    return dialogs.length > 0;
                }"""
            )
        )

    async def _configure_bibliography_download_dialog(self, page, download_limit: int) -> None:
        result = await page.evaluate(
            """({ limit, template }) => {
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const visibleElements = (root, selector) => Array.from(root.querySelectorAll(selector)).filter(visible);
                const setValue = (el, value) => {
                    const proto = Object.getPrototypeOf(el);
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(el, value);
                    } else {
                        el.value = value;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                };
                const clickNearestInput = (root, text) => {
                    const label = visibleElements(root, 'label,span,div,p').find((el) => (el.innerText || '').trim().includes(text));
                    if (!label) return false;
                    const container = label.closest('label,li,tr,.row,.form-group,div') || label.parentElement || root;
                    const radio = visibleElements(container, 'input[type="radio"]').find((el) => !el.disabled);
                    if (radio) {
                        radio.click();
                        return true;
                    }
                    label.click();
                    return true;
                };
                const dialogs = visibleElements(document, 'div,section,article,[role="dialog"]')
                    .filter((el) => {
                        const text = el.innerText || '';
                        return text.includes('下载著录项') && text.includes('导出范围');
                    })
                    .sort((a, b) => {
                        const ar = a.getBoundingClientRect();
                        const br = b.getBoundingClientRect();
                        return (ar.width * ar.height) - (br.width * br.height);
                    });
                const dialog = dialogs[0];
                if (!dialog) return { ok: false, error: '未找到下载著录项弹窗。' };

                clickNearestInput(dialog, '范围从');

                const rangeInputs = visibleElements(dialog, 'input')
                    .filter((el) => !el.disabled && !['radio', 'checkbox', 'hidden', 'file'].includes((el.type || '').toLowerCase()));
                if (rangeInputs.length < 2) return { ok: false, error: '未找到下载范围输入框。' };
                setValue(rangeInputs[0], '1');
                setValue(rangeInputs[1], String(limit));

                const xlsCandidate = visibleElements(dialog, 'button,a,span,div,i,label')
                    .filter((el) => {
                        const text = [
                            el.innerText || '',
                            el.getAttribute('title') || '',
                            el.getAttribute('aria-label') || '',
                            el.getAttribute('class') || ''
                        ].join(' ');
                        return /\\bXLS\\b|\\bXLSX\\b|xls|xlsx/i.test(text);
                    })
                    .sort((a, b) => {
                        const ar = a.getBoundingClientRect();
                        const br = b.getBoundingClientRect();
                        return (ar.width * ar.height) - (br.width * br.height);
                    })[0];
                if (xlsCandidate) {
                    xlsCandidate.scrollIntoView({ block: 'center', inline: 'center' });
                    xlsCandidate.click();
                }

                const selects = visibleElements(dialog, 'select');
                for (const select of selects) {
                    const option = Array.from(select.options || []).find((item) => item.text.trim() === template || item.value === template);
                    if (option) {
                        select.value = option.value;
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        break;
                    }
                }

                const text = dialog.innerText || '';
                if (!text.includes(template)) return { ok: false, error: `未找到 ${template} 下载模板。` };

                const pdfSwitches = visibleElements(dialog, 'input[type="checkbox"]');
                for (const item of pdfSwitches) {
                    const nearby = (item.closest('label,li,tr,.row,.form-group,div') || dialog).innerText || '';
                    if (nearby.includes('同时下载PDF') && item.checked) item.click();
                }

                return { ok: true };
            }""",
            {"limit": download_limit, "template": "wjl01"},
        )
        if not result.get("ok"):
            raise PatentHubAutomationError(result.get("error") or "下载著录项弹窗配置失败。")

    async def _has_dialog_download_button(self, page) -> bool:
        return bool(await page.evaluate(self._dialog_download_button_script("check")))

    async def _click_dialog_download_button(self, page) -> bool:
        return bool(await page.evaluate(self._dialog_download_button_script("click")))

    @staticmethod
    def _dialog_download_button_script(mode: str) -> str:
        return f"""() => {{
            const visible = (el) => {{
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && rect.width > 0
                    && rect.height > 0;
            }};
            const elements = (root, selector) => Array.from(root.querySelectorAll(selector)).filter(visible);
            const dialogs = elements(document, 'div,section,article,[role="dialog"]')
                .filter((el) => {{
                    const text = el.innerText || '';
                    return text.includes('下载著录项') && text.includes('导出范围');
                }})
                .sort((a, b) => {{
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (ar.width * ar.height) - (br.width * br.height);
                }});
            const dialog = dialogs[0];
            if (!dialog) return false;
            const candidates = elements(dialog, 'button,a,[role="button"],input[type="button"],input[type="submit"]')
                .filter((el) => {{
                    const text = (el.innerText || el.value || '').trim();
                    return text === '下载';
                }});
            const button = candidates[0];
            if (!button) return false;
            if ('{mode}' === 'click') {{
                button.scrollIntoView({{ block: 'center', inline: 'center' }});
                button.click();
            }}
            return true;
        }}"""

    @staticmethod
    def _is_login_url(url: str) -> bool:
        return "/user/login" in (url or "")

    @staticmethod
    async def _notify(status_callback: StatusCallback, status: str, progress: int, message: str) -> None:
        await status_callback(status, progress, message)

    @staticmethod
    async def _check_cancel(cancel_event: asyncio.Event) -> None:
        if cancel_event.is_set():
            raise asyncio.CancelledError

    @staticmethod
    async def _wait_continue_or_cancel(continue_event: asyncio.Event, cancel_event: asyncio.Event) -> None:
        while True:
            if cancel_event.is_set():
                raise asyncio.CancelledError
            if continue_event.is_set():
                continue_event.clear()
                return
            await asyncio.sleep(0.5)
