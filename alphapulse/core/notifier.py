import asyncio
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH = 4096
DEFAULT_MAX_RETRIES = 3


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        send_file: bool = False,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        # If not provided explicitly, try loading from Config
        if not bot_token or not chat_id:
            try:
                from alphapulse.core.config import Config
                cfg = Config()
                bot_token = bot_token or getattr(cfg, "TELEGRAM_BOT_TOKEN", "")
                chat_id = chat_id or getattr(cfg, "TELEGRAM_CHAT_ID", "")
                send_file = send_file or getattr(cfg, "TELEGRAM_SEND_FILE", False)
                max_retries = getattr(cfg, "MAX_RETRIES", DEFAULT_MAX_RETRIES)
            except Exception:
                pass

        self.bot_token = bot_token
        self.chat_id = chat_id
        self.send_file = send_file
        self.max_retries = max_retries

    async def send(
        self,
        title: str,
        category: str,
        analysis: str,
        url: str,
        report_path: Path | None = None,
        source_tag: str = "",
    ) -> bool:
        message = self._build_message(title, category, analysis, url, source_tag)
        parts = self._split_message(message)

        for part in parts:
            success = await self._send_message(part)
            if not success:
                return False

        if self.send_file and report_path and report_path.exists():
            await self._send_document(report_path)

        return True

    async def send_test(self) -> bool:
        return await self._send_message("AlphaPulse 텔레그램 연결 테스트 성공!")

    def _build_message(self, title: str, category: str, analysis: str, url: str, source_tag: str = "") -> str:
        html_analysis = self._markdown_to_html(analysis)
        header = f"<b>{source_tag} 새 글 알림</b>" if source_tag else "<b>새 글 알림</b>"
        return (
            f'{header} | <i>{category or "미분류"}</i>\n\n'
            f"<b>제목:</b> {self._escape_html(title)}\n\n"
            f"{html_analysis}\n\n"
            f'<a href="{url}">원문 보기</a>'
        )

    def _markdown_to_html(self, md: str) -> str:
        text = md
        text = re.sub(r"^##\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
        text = re.sub(r"^#\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"^- ", "• ", text, flags=re.MULTILINE)
        return text

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _split_message(self, message: str) -> list[str]:
        if len(message) <= MAX_MESSAGE_LENGTH:
            return [message]

        parts = []
        while message:
            if len(message) <= MAX_MESSAGE_LENGTH:
                parts.append(message)
                break
            split_at = message.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = MAX_MESSAGE_LENGTH
            parts.append(message[:split_at])
            message = message[split_at:].lstrip("\n")
        return parts

    async def _send_message(self, text: str) -> bool:
        url = TELEGRAM_API.format(token=self.bot_token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        return True
                    if resp.status_code == 429:
                        retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                        logger.warning(f"Rate limited, {retry_after}초 대기")
                        await asyncio.sleep(retry_after)
                        continue
                    logger.error(f"텔레그램 전송 실패: {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"텔레그램 전송 에러 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5)

        return False

    async def _send_document(self, filepath: Path) -> bool:
        url = TELEGRAM_API.format(token=self.bot_token, method="sendDocument")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(filepath, "rb") as f:
                    resp = await client.post(
                        url,
                        data={"chat_id": self.chat_id},
                        files={"document": (filepath.name, f)},
                    )
                    return resp.status_code == 200
        except Exception as e:
            logger.error(f"파일 전송 실패: {e}")
            return False
