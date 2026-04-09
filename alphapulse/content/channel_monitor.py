import logging
from datetime import datetime

from telethon import TelegramClient, events

from alphapulse.content.aggregator import MessageAggregator
from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()


class TelegramChannelMonitor:
    def __init__(
        self,
        api_id: str = _cfg.TELEGRAM_API_ID,
        api_hash: str = _cfg.TELEGRAM_API_HASH,
        phone: str = _cfg.TELEGRAM_PHONE,
        channel_ids: list[str] = None,
        analyzer=None,
        reporter=None,
        notifier=None,
        aggregation_window: int = _cfg.AGGREGATION_WINDOW,
        session_path: str = "blogpulse_session",
        reports_dir: str = _cfg.REPORTS_DIR,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.channel_ids = channel_ids or _cfg.CHANNEL_IDS
        self.analyzer = analyzer
        self.reporter = reporter
        self.notifier = notifier
        self.reports_dir = reports_dir

        self.client = TelegramClient(session_path, int(api_id), api_hash)
        self.aggregator = MessageAggregator(
            window_seconds=aggregation_window,
            on_thread_ready=self._on_thread_ready,
        )

        # Build a set of target IDs (strings for flexible matching)
        self._target_ids = set()
        for cid in self.channel_ids:
            self._target_ids.add(str(cid).strip().lstrip("@"))

    async def start(self):
        logger.info("텔레그램 채널 모니터 시작...")
        await self.client.start(phone=self.phone)
        logger.info(f"텔레그램 로그인 완료. 모니터링 채널: {self.channel_ids}")

        @self.client.on(events.NewMessage)
        async def handler(event):
            await self._handle_message(event)

        logger.info("메시지 리스닝 시작...")
        await self.client.run_until_disconnected()

    async def _handle_message(self, event):
        try:
            chat = await event.get_chat()
            if not self._should_monitor(chat):
                return

            text = event.message.text or event.message.message
            if not text:
                return

            channel_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(chat.id)
            timestamp = event.message.date.replace(tzinfo=None) if event.message.date else datetime.now()

            await self.aggregator.add_message(
                channel_id=chat.id,
                channel_name=channel_name,
                text=text,
                timestamp=timestamp,
            )
        except Exception as e:
            logger.error(f"메시지 처리 에러: {e}")

    def _should_monitor(self, entity) -> bool:
        entity_id = str(entity.id)
        entity_username = getattr(entity, "username", "") or ""
        return (
            entity_id in self._target_ids
            or entity_username.lower() in {t.lower() for t in self._target_ids}
        )

    async def _on_thread_ready(self, thread: dict):
        try:
            logger.info(f'[채널분석] 글타래 분석 시작: "{thread["title"]}"')

            analysis = await self.analyzer.analyze(thread["title"], thread["content"])

            report_path = self.reporter.save(
                title=thread["title"],
                url="",
                published=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                category="채널분석",
                analysis=analysis,
                original_content=thread["content"],
                source_tag="[채널분석]",
            )

            if self.notifier:
                await self.notifier.send(
                    title=thread["title"],
                    category="채널분석",
                    analysis=analysis,
                    url="",
                    report_path=report_path,
                    source_tag="[채널분석]",
                )

            logger.info(f'[채널분석] 완료: "{thread["title"]}" → {report_path.name}')
        except Exception as e:
            logger.error(f'[채널분석] 글타래 분석 실패: "{thread.get("title", "?")}": {e}')

    async def list_channels(self):
        await self.client.start(phone=self.phone)
        print("\n=== 구독 중인 채널 목록 ===\n")
        async for dialog in self.client.iter_dialogs():
            if dialog.is_channel:
                entity = dialog.entity
                username = f"@{entity.username}" if entity.username else "(username 없음)"
                print(f"  ID: {entity.id:>15}  |  {username:<25}  |  {dialog.name}")
        print()
        await self.client.disconnect()

    async def stop(self):
        if self.client.is_connected():
            await self.client.disconnect()
            logger.info("텔레그램 채널 모니터 종료")
