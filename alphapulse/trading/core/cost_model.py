"""거래 비용 모델.

수수료, 세금, 슬리피지를 계산한다. 백테스트/Paper/실매매 모두 동일 모델을 사용한다.
"""

from dataclasses import dataclass

from alphapulse.trading.core.models import Order


@dataclass
class CostModel:
    """거래 비용 모델.

    Attributes:
        commission_rate: 수수료율 (매수+매도 양방향). 기본 0.015%.
        tax_rate_stock: 주식 매도세. 기본 0.18%.
        tax_rate_etf: ETF 매도세. 기본 0% (면제).
        slippage_model: 슬리피지 모델 ("volume_based" | "fixed" | "none").
    """
    commission_rate: float = 0.00015
    tax_rate_stock: float = 0.0018
    tax_rate_etf: float = 0.0
    slippage_model: str = "volume_based"

    def calculate_commission(self, amount: float) -> float:
        """수수료를 계산한다.

        Args:
            amount: 거래 금액 (원).

        Returns:
            수수료 (원).
        """
        return amount * self.commission_rate

    def calculate_tax(self, amount: float, is_etf: bool) -> float:
        """매도세를 계산한다.

        Args:
            amount: 거래 금액 (원).
            is_etf: ETF 여부.

        Returns:
            세금 (원). ETF는 0.
        """
        rate = self.tax_rate_etf if is_etf else self.tax_rate_stock
        return amount * rate

    def estimate_slippage(self, order: Order, avg_volume: int) -> float:
        """체결가 대비 예상 슬리피지를 추정한다.

        거래대금 대비 주문량 비율로 시장 충격(market impact)을 추정한다.

        Args:
            order: 주문.
            avg_volume: 일평균 거래량 (주).

        Returns:
            슬리피지 비율 (0.001 = 0.1%).
        """
        if self.slippage_model == "none":
            return 0.0
        if self.slippage_model == "fixed":
            return 0.001

        price = order.price or 0
        order_amount = order.quantity * price
        avg_daily_amount = avg_volume * price
        if avg_daily_amount == 0:
            return 0.003

        impact_ratio = order_amount / avg_daily_amount
        if impact_ratio < 0.01:
            return 0.0
        elif impact_ratio < 0.05:
            return 0.001
        else:
            return 0.003

    def total_cost(self, order: Order, filled_price: float,
                   is_etf: bool, avg_volume: int) -> dict:
        """주문 총 비용을 계산한다.

        Args:
            order: 주문.
            filled_price: 체결가 (원).
            is_etf: ETF 여부.
            avg_volume: 일평균 거래량 (주).

        Returns:
            {"commission": float, "tax": float, "slippage": float}.
        """
        amount = order.quantity * filled_price
        return {
            "commission": self.calculate_commission(amount),
            "tax": self.calculate_tax(amount, is_etf) if order.side == "SELL" else 0,
            "slippage": self.estimate_slippage(order, avg_volume),
        }
