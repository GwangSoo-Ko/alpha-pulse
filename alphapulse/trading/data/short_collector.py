"""공매도/신용잔고 수집기.

현재는 저장소 인터페이스만 제공한다.
실제 데이터 수집은 KRX/네이버 스크래퍼 구현 후 추가한다.
데이터 소스 검증 프로토콜에 따라 구현 단계에서 소스를 확정한다.
"""

import logging
from pathlib import Path

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class ShortCollector:
    """공매도/신용잔고 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, code: str, start: str, end: str) -> None:
        """공매도/신용잔고를 수집하여 DB에 저장한다.

        NOTE: 데이터 소스 확정 후 구현 예정.
              KRX 정보데이터시스템 또는 네이버 금융 스크래퍼 구현 필요.
              구현 시 데이터 소스 검증 프로토콜 준수:
              1. 1순위 소스 API 호출 테스트
              2. 반환 데이터 형식/품질 확인
              3. 실패 시 2순위 폴백

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        logger.warning("공매도 수집기 미구현: %s. 데이터 소스 확정 후 구현 예정.", code)
