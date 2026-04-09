"""TradingScheduler — KRX 시간대 기반 스케줄링.

한국 주식시장 운영 시간에 맞춰 매매 파이프라인 단계를 실행한다.
KRXCalendar를 사용하여 공휴일에는 자동으로 건너뛴다.
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, time

logger = logging.getLogger(__name__)


class TradingScheduler:
    """한국 시장 시간대 기반 스케줄러.

    SCHEDULE 딕셔너리의 각 단계를 정해진 시각에 실행한다.
    run_daemon()으로 데몬 모드 실행, run_once()로 단일 실행.

    Attributes:
        SCHEDULE: 단계별 실행 시각 (HH:MM 형식).
        engine: TradingEngine 인스턴스.
        calendar: KRXCalendar 인스턴스.
    """

    SCHEDULE = OrderedDict(
        [
            ("data_update", "08:00"),
            ("analysis", "08:15"),
            ("portfolio", "08:40"),
            ("pre_market_alert", "08:50"),
            ("market_open", "09:00"),
            ("midday_check", "12:30"),
            ("market_close", "15:30"),
            ("post_market", "16:00"),
        ]
    )

    def __init__(self, engine, calendar) -> None:
        """TradingScheduler를 초기화한다.

        Args:
            engine: TradingEngine 인스턴스.
            calendar: KRXCalendar 인스턴스.
        """
        self.engine = engine
        self.calendar = calendar

    def is_active_day(self, date: str) -> bool:
        """지정 날짜가 거래일인지 확인한다.

        Args:
            date: 날짜 (YYYYMMDD).

        Returns:
            거래일이면 True.
        """
        return self.calendar.is_trading_day(date)

    def should_run_phase(self, phase: str, current_time: time) -> bool:
        """현재 시각에 지정 단계를 실행해야 하는지 판단한다.

        Args:
            phase: 단계 이름 (예: "data_update").
            current_time: 현재 시각.

        Returns:
            실행 시각 이후이면 True.
        """
        phase_time_str = self.SCHEDULE.get(phase)
        if not phase_time_str:
            return False
        h, m = map(int, phase_time_str.split(":"))
        phase_time = time(h, m)
        return current_time >= phase_time

    def get_next_phase(self, current_time: time) -> tuple[str | None, str | None]:
        """현재 시각 이후의 다음 실행 단계를 반환한다.

        Args:
            current_time: 현재 시각.

        Returns:
            (단계명, 시각 문자열) 또는 (None, None) — 모든 단계 완료 시.
        """
        for phase, time_str in self.SCHEDULE.items():
            h, m = map(int, time_str.split(":"))
            phase_time = time(h, m)
            if current_time < phase_time:
                return phase, time_str
        return None, None

    async def run_once(self, date: str | None = None) -> dict | None:
        """일일 매매 사이클을 1회 실행한다.

        공휴일이면 실행하지 않고 None을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD). None이면 오늘.

        Returns:
            실행 결과 딕셔너리 또는 None.
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        if not self.is_active_day(date):
            logger.info("공휴일/비거래일: %s — 건너뜀", date)
            return None

        logger.info("매매 사이클 시작: %s", date)
        return await self.engine.run_daily(date=date)

    async def run_daemon(self) -> None:
        """스케줄 기반 데몬 모드.

        거래일에는 SCHEDULE에 따라 단계를 실행하고,
        비거래일에는 다음 거래일까지 대기한다.
        """
        logger.info("데몬 모드 시작")

        while True:
            now = datetime.now()
            today = now.strftime("%Y%m%d")

            if not self.is_active_day(today):
                next_day = self.calendar.next_trading_day(today)
                logger.info("비거래일. 다음 거래일: %s", next_day)
                await self._sleep_until_date(next_day, "07:50")
                continue

            # 당일 전체 실행
            await self.run_once(date=today)

            # 다음 거래일까지 대기
            next_day = self.calendar.next_trading_day(today)
            logger.info("당일 사이클 완료. 다음 거래일: %s", next_day)
            await self._sleep_until_date(next_day, "07:50")

    async def _sleep_until_date(self, date: str, time_str: str) -> None:
        """지정 날짜+시각까지 대기한다.

        Args:
            date: 대기할 날짜 (YYYYMMDD).
            time_str: 대기할 시각 (HH:MM).
        """
        h, m = map(int, time_str.split(":"))
        target = datetime.strptime(date, "%Y%m%d").replace(hour=h, minute=m)
        now = datetime.now()
        delta = (target - now).total_seconds()
        if delta > 0:
            logger.info("대기: %s %s (%.0f초)", date, time_str, delta)
            await asyncio.sleep(delta)
