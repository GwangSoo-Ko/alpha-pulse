import asyncio
import logging
from datetime import datetime
from typing import Callable, Awaitable

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()


class MessageAggregator:
    def __init__(
        self,
        window_seconds: int = _cfg.AGGREGATION_WINDOW,
        on_thread_ready: Callable[[dict], Awaitable[None]] | None = None,
        min_chars: int = 20,
    ):
        self.window = window_seconds
        self.on_thread_ready = on_thread_ready
        self.min_chars = min_chars
        self.buffers: dict[int, list[dict]] = {}
        self.channel_names: dict[int, str] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    async def add_message(
        self, channel_id: int, channel_name: str, text: str | None, timestamp: datetime
    ):
        if not text or not text.strip():
            return

        if channel_id not in self.buffers:
            self.buffers[channel_id] = []
        self.channel_names[channel_id] = channel_name

        self.buffers[channel_id].append({
            "text": text.strip(),
            "timestamp": timestamp,
        })

        # Cancel existing timer and schedule new one
        if channel_id in self._tasks:
            self._tasks[channel_id].cancel()
        self._tasks[channel_id] = asyncio.create_task(self._delayed_flush(channel_id))

        logger.debug(f"[{channel_name}] 메시지 버퍼링 (총 {len(self.buffers[channel_id])}개)")

    async def _delayed_flush(self, channel_id: int):
        await asyncio.sleep(self.window)
        await self._flush(channel_id)

    async def _flush(self, channel_id: int):
        messages = self.buffers.pop(channel_id, [])
        channel_name = self.channel_names.pop(channel_id, "unknown")
        self._tasks.pop(channel_id, None)

        if not messages:
            return

        total_text = " ".join(m["text"] for m in messages)
        if len(total_text) < self.min_chars:
            logger.info(f"[{channel_name}] 글타래 너무 짧음 ({len(total_text)}자), 스킵")
            return

        thread = self.format_thread(channel_name, messages)
        logger.info(f"[{channel_name}] 글타래 확정: {len(messages)}개 메시지")

        if self.on_thread_ready:
            await self.on_thread_ready(thread)

    def format_thread(self, channel_name: str, messages: list[dict]) -> dict:
        first_time = messages[0]["timestamp"].strftime("%H:%M")
        last_time = messages[-1]["timestamp"].strftime("%H:%M")
        date_str = messages[0]["timestamp"].strftime("%Y-%m-%d")

        title = f"[{channel_name}] {date_str} {first_time}~{last_time} ({len(messages)}개 메시지)"

        content_lines = []
        for msg in messages:
            time_str = msg["timestamp"].strftime("%H:%M")
            content_lines.append(f"{time_str} {msg['text']}")

        content = "\n".join(content_lines)

        return {
            "channel_name": channel_name,
            "title": title,
            "content": content,
            "messages": messages,
            "message_count": len(messages),
        }
