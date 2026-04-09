"""TradingSafeguard — 실매매 안전장치.

LIVE_TRADING_ENABLED 환경변수 검사, 사용자 수동 확인,
일일 주문 횟수/금액 한도를 관리한다.
"""

import logging

logger = logging.getLogger(__name__)


class TradingSafeguard:
    """실매매 전용 안전장치.

    이중 안전장치 역할:
    1. LIVE_TRADING_ENABLED=true 환경변수 필수
    2. confirm_live_start()로 터미널에서 사용자 수동 확인
    3. 일일 주문 횟수/금액 한도 제한

    Attributes:
        live_enabled: 실매매 활성화 여부.
        max_daily_orders: 일일 최대 주문 횟수.
        max_daily_amount: 일일 최대 주문 금액 (원).
        today_order_count: 오늘 누적 주문 횟수.
        today_order_amount: 오늘 누적 주문 금액.
    """

    def __init__(self, config: dict) -> None:
        """TradingSafeguard를 초기화한다.

        Args:
            config: 설정 딕셔너리. 키: LIVE_TRADING_ENABLED, MAX_DAILY_ORDERS, MAX_DAILY_AMOUNT.
        """
        self.live_enabled: bool = config.get("LIVE_TRADING_ENABLED", False)
        self.max_daily_orders: int = config.get("MAX_DAILY_ORDERS", 50)
        self.max_daily_amount: float = config.get("MAX_DAILY_AMOUNT", 50_000_000)
        self.today_order_count: int = 0
        self.today_order_amount: float = 0

    def check_live_allowed(self) -> bool:
        """LIVE_TRADING_ENABLED 활성화 여부를 확인한다.

        Returns:
            True (활성화 상태).

        Raises:
            RuntimeError: 비활성화 상태인 경우.
        """
        if not self.live_enabled:
            raise RuntimeError(
                "실매매가 비활성화 상태입니다. "
                "LIVE_TRADING_ENABLED=true 설정 후 재시작하세요."
            )
        return True

    def confirm_live_start(self, account_no: str) -> bool:
        """터미널에서 사용자 수동 확인을 받는다.

        Args:
            account_no: 계좌번호 (표시용).

        Returns:
            사용자가 'yes'를 입력하면 True, 그 외 False.
        """
        response = input(
            f"실매매를 시작합니다.\n"
            f"계좌: {account_no}\n"
            f"확인하시겠습니까? (yes/no): "
        )
        confirmed = response.strip().lower() == "yes"
        if confirmed:
            logger.info("실매매 시작 확인. 계좌: %s", account_no)
        else:
            logger.info("실매매 시작 취소. 사용자 입력: %s", response.strip())
        return confirmed

    def check_daily_limit(self, today_orders: int, today_amount: float) -> bool:
        """일일 주문 한도를 검사한다.

        Args:
            today_orders: 오늘 누적 주문 횟수.
            today_amount: 오늘 누적 주문 금액 (원).

        Returns:
            True (한도 내).

        Raises:
            RuntimeError: 한도 초과 시.
        """
        if today_orders >= self.max_daily_orders:
            raise RuntimeError(
                f"일일 주문 한도 초과: {today_orders}/{self.max_daily_orders}"
            )
        if today_amount >= self.max_daily_amount:
            raise RuntimeError(
                f"일일 금액 한도 초과: {today_amount:,.0f}/{self.max_daily_amount:,.0f}"
            )
        return True

    def record_order(self, amount: float) -> None:
        """주문을 기록하여 일일 누적 카운터를 증가시킨다.

        Args:
            amount: 주문 금액 (원).
        """
        self.today_order_count += 1
        self.today_order_amount += amount

    def reset_daily(self) -> None:
        """일일 카운터를 초기화한다. 새로운 거래일 시작 시 호출."""
        self.today_order_count = 0
        self.today_order_amount = 0
        logger.info("일일 주문 카운터 초기화")
