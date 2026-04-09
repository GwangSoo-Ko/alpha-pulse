"""한국거래소(KRX) 영업일 캘린더.

pykrx의 내장 캘린더를 활용하되, 폴백으로 자체 공휴일 테이블을 유지한다.
"""

from datetime import datetime, timedelta


# 한국 고정 공휴일 (월/일)
_FIXED_HOLIDAYS = {
    (1, 1),    # 신정
    (3, 1),    # 삼일절
    (5, 5),    # 어린이날
    (6, 6),    # 현충일
    (8, 15),   # 광복절
    (10, 3),   # 개천절
    (10, 9),   # 한글날
    (12, 25),  # 크리스마스
}

# 연도별 변동 공휴일 (음력 명절, 대체공휴일 등)
# 매년 초에 KRX 공시 기반으로 갱신해야 한다.
_VARIABLE_HOLIDAYS: dict[int, set[tuple[int, int]]] = {
    2025: {
        (1, 28), (1, 29), (1, 30),   # 설날 연휴
        (5, 6),                        # 대체공휴일
        (10, 5), (10, 6), (10, 7),    # 추석 연휴
    },
    2026: {
        (2, 16), (2, 17), (2, 18),   # 설날 연휴
        (5, 6),                        # 대체공휴일
        (9, 24), (9, 25), (9, 26),   # 추석 연휴 (26은 토요일)
    },
}


class KRXCalendar:
    """한국거래소 영업일 관리.

    평일이면서 공휴일이 아닌 날을 거래일로 판단한다.
    """

    def is_trading_day(self, date: str) -> bool:
        """해당 날짜가 거래일인지 판단한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).

        Returns:
            거래일이면 True.
        """
        dt = self._parse(date)
        if dt.weekday() >= 5:  # 토(5), 일(6)
            return False
        return not self._is_holiday(dt)

    def next_trading_day(self, date: str) -> str:
        """다음 거래일을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD).

        Returns:
            다음 거래일 문자열 (YYYYMMDD).
        """
        dt = self._parse(date) + timedelta(days=1)
        while not self.is_trading_day(dt.strftime("%Y%m%d")):
            dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")

    def prev_trading_day(self, date: str) -> str:
        """이전 거래일을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD).

        Returns:
            이전 거래일 문자열 (YYYYMMDD).
        """
        dt = self._parse(date) - timedelta(days=1)
        while not self.is_trading_day(dt.strftime("%Y%m%d")):
            dt -= timedelta(days=1)
        return dt.strftime("%Y%m%d")

    def trading_days_between(self, start: str, end: str) -> list[str]:
        """구간 내 거래일 목록을 반환한다.

        Args:
            start: 시작일 (YYYYMMDD, 포함).
            end: 종료일 (YYYYMMDD, 포함).

        Returns:
            거래일 문자열 리스트.
        """
        result = []
        dt = self._parse(start)
        end_dt = self._parse(end)
        while dt <= end_dt:
            date_str = dt.strftime("%Y%m%d")
            if self.is_trading_day(date_str):
                result.append(date_str)
            dt += timedelta(days=1)
        return result

    def is_half_day(self, date: str) -> bool:
        """해당 날짜가 반일장(단축거래일)인지 판단한다.

        현재는 스텁으로 항상 False를 반환한다. KRX가 반일장을
        공시하면 해당 날짜를 추가해야 한다 (거의 발생하지 않음).

        Args:
            date: 날짜 문자열 (YYYYMMDD).

        Returns:
            반일장이면 True. 현재는 항상 False.
        """
        return False

    def _is_holiday(self, dt: datetime) -> bool:
        """공휴일 여부를 확인한다."""
        md = (dt.month, dt.day)
        if md in _FIXED_HOLIDAYS:
            return True
        year_holidays = _VARIABLE_HOLIDAYS.get(dt.year, set())
        return md in year_holidays

    @staticmethod
    def _parse(date: str) -> datetime:
        """YYYYMMDD 문자열을 datetime으로 변환한다."""
        return datetime.strptime(date, "%Y%m%d")
