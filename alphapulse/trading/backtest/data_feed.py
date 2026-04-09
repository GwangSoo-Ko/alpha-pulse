"""히스토리 데이터 피드 — look-ahead bias 방지.

HistoricalDataFeed는 현재 날짜를 추적하며, 미래 데이터 접근을 차단한다.
백테스트 엔진이 advance_to()로 날짜를 전진시키고, 전략/포트폴리오가 데이터를 요청한다.
"""

from alphapulse.trading.core.models import OHLCV


class HistoricalDataFeed:
    """히스토리 데이터 피드.

    미래 데이터 접근을 차단하여 look-ahead bias를 방지한다.
    advance_to()로 현재 날짜를 전진시키며, end > current_date인 요청은 거부한다.

    Attributes:
        current_date: 현재 시뮬레이션 날짜 (YYYYMMDD).
    """

    def __init__(self, all_data: dict[str, list[OHLCV]]) -> None:
        """초기화.

        Args:
            all_data: 종목코드 → OHLCV 리스트 매핑. 날짜순 정렬 가정.
        """
        self._all_data = all_data
        self.current_date: str = ""

    def advance_to(self, date: str) -> None:
        """현재 날짜를 전진시킨다.

        이 날짜 이후 데이터는 접근 불가.

        Args:
            date: 새로운 현재 날짜 (YYYYMMDD).
        """
        self.current_date = date

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """OHLCV 데이터를 반환한다. 미래 데이터 요청 시 AssertionError.

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD, 포함).
            end: 종료일 (YYYYMMDD, 포함).

        Returns:
            해당 구간의 OHLCV 리스트.

        Raises:
            AssertionError: end > current_date인 경우.
        """
        assert end <= self.current_date, (
            f"Look-ahead bias! Requested {end} but current date is {self.current_date}"
        )
        bars = self._all_data.get(code, [])
        return [bar for bar in bars if start <= bar.date <= end]

    def get_latest_price(self, code: str) -> float:
        """현재 날짜의 종가를 반환한다.

        Args:
            code: 종목코드.

        Returns:
            종가. 데이터 없으면 0.0.
        """
        bar = self.get_bar(code)
        return bar.close if bar else 0.0

    def get_bar(self, code: str) -> OHLCV | None:
        """현재 날짜의 OHLCV 바를 반환한다.

        Args:
            code: 종목코드.

        Returns:
            OHLCV 또는 None.
        """
        bars = self._all_data.get(code, [])
        for bar in bars:
            if bar.date == self.current_date:
                return bar
        return None

    def get_available_codes(self) -> list[str]:
        """등록된 종목 코드 목록을 반환한다."""
        return list(self._all_data.keys())

    # --- DataProvider Protocol stub methods ---
    # HistoricalDataFeed는 백테스트 데이터 피드이므로 재무, 수급, 공매도 데이터를
    # 직접 제공하지 않는다. DataProvider Protocol 구조적 호환을 위해 빈 dict 반환.

    def get_financials(self, code: str) -> dict:
        """재무제표 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}

    def get_investor_flow(self, code: str, days: int) -> dict:
        """투자자별 매매동향 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}

    def get_short_interest(self, code: str, days: int) -> dict:
        """공매도 잔고 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}
