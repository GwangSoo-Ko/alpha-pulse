"""데몬 모드 스케줄러 — 매일 지정 시간에 브리핑 실행."""

import logging
import time as time_module
from datetime import datetime, time

logger = logging.getLogger(__name__)

DEFAULT_BRIEFING_TIME = "08:30"


def parse_time(time_str: str | None) -> tuple[int, int]:
    """HH:MM 문자열을 (hour, minute) 튜플로 파싱."""
    try:
        parts = (time_str or DEFAULT_BRIEFING_TIME).split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        logger.warning(f"잘못된 시간 형식: {time_str}, 기본값 사용: {DEFAULT_BRIEFING_TIME}")
        return 8, 30


def should_run_now(current: time, target: time, tolerance_minutes: int = 1) -> bool:
    """현재 시간이 목표 시간 ± tolerance 이내인지 확인."""
    current_mins = current.hour * 60 + current.minute
    target_mins = target.hour * 60 + target.minute
    return abs(current_mins - target_mins) <= tolerance_minutes


def run_scheduler(orchestrator, briefing_time: str | None = None,
                  send_telegram: bool = True):
    """매일 지정 시간에 브리핑을 실행하는 데몬 루프."""
    hour, minute = parse_time(briefing_time)
    target = time(hour, minute)
    logger.info(f"브리핑 스케줄러 시작: 매일 {hour:02d}:{minute:02d}")

    ran_today = False

    while True:
        now = datetime.now()
        current = now.time()

        if should_run_now(current, target) and not ran_today:
            logger.info("브리핑 실행 시작")
            try:
                orchestrator.run(send_telegram=send_telegram)
                logger.info("브리핑 완료")
            except Exception as e:
                logger.error(f"브리핑 실패: {e}")
            ran_today = True
        elif not should_run_now(current, target, tolerance_minutes=5):
            ran_today = False

        time_module.sleep(30)
