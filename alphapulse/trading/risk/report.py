"""리스크 리포트 생성.

일일 리스크 현황을 요약하는 리포트를 생성한다.
"""

import logging
from dataclasses import dataclass, field

from alphapulse.trading.core.models import PortfolioSnapshot
from alphapulse.trading.risk.limits import RiskAlert
from alphapulse.trading.risk.stress_test import StressResult

logger = logging.getLogger(__name__)


@dataclass
class RiskReport:
    """일일 리스크 리포트.

    Attributes:
        date: 기준 날짜 (YYYYMMDD).
        drawdown_pct: 현재 드로다운 (%).
        drawdown_status: 드로다운 상태 ("NORMAL" | "WARN" | "DELEVERAGE").
        var_95: 95% VaR.
        cvar_95: 95% CVaR.
        alerts: 리스크 경고 목록.
        stress_results: 스트레스 테스트 결과.
        sector_concentration: 섹터별 집중도.
    """

    date: str
    drawdown_pct: float
    drawdown_status: str
    var_95: float
    cvar_95: float
    alerts: list[RiskAlert] = field(default_factory=list)
    stress_results: dict[str, StressResult] = field(default_factory=dict)
    sector_concentration: dict[str, float] = field(default_factory=dict)


class RiskReportGenerator:
    """리스크 리포트 생성기."""

    def generate(
        self,
        portfolio: PortfolioSnapshot,
        drawdown_status: str,
        var_95: float,
        cvar_95: float,
        stress_results: dict[str, StressResult],
        max_sector_weight: float = 0.30,
    ) -> RiskReport:
        """일일 리스크 리포트를 생성한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            drawdown_status: 드로다운 상태 문자열.
            var_95: 95% VaR.
            cvar_95: 95% CVaR.
            stress_results: 스트레스 테스트 결과.
            max_sector_weight: 섹터 집중도 경고 한도.

        Returns:
            RiskReport 인스턴스.
        """
        sector_conc = self.calculate_sector_concentration(portfolio)
        alerts = self.check_concentration_alerts(
            portfolio, max_sector_weight,
        )

        return RiskReport(
            date=portfolio.date,
            drawdown_pct=abs(portfolio.drawdown),
            drawdown_status=drawdown_status,
            var_95=var_95,
            cvar_95=cvar_95,
            alerts=alerts,
            stress_results=stress_results,
            sector_concentration=sector_conc,
        )

    def calculate_sector_concentration(
        self,
        portfolio: PortfolioSnapshot,
    ) -> dict[str, float]:
        """섹터별 집중도를 계산한다.

        Args:
            portfolio: 포트폴리오 스냅샷.

        Returns:
            섹터명 → 비중 매핑.
        """
        sector_weights: dict[str, float] = {}
        for pos in portfolio.positions:
            sector = pos.stock.sector or "기타"
            sector_weights[sector] = (
                sector_weights.get(sector, 0.0) + pos.weight
            )
        return sector_weights

    def check_concentration_alerts(
        self,
        portfolio: PortfolioSnapshot,
        max_sector_weight: float = 0.30,
    ) -> list[RiskAlert]:
        """섹터 집중도 경고를 생성한다.

        Args:
            portfolio: 포트폴리오 스냅샷.
            max_sector_weight: 섹터당 최대 비중.

        Returns:
            RiskAlert 리스트.
        """
        sector_conc = self.calculate_sector_concentration(portfolio)
        alerts = []

        for sector, weight in sector_conc.items():
            if weight > max_sector_weight:
                alerts.append(
                    RiskAlert(
                        level="WARNING",
                        category="concentration",
                        message=f"{sector} 섹터 집중도 {weight:.0%} > 한도 {max_sector_weight:.0%}",
                        current_value=weight,
                        limit_value=max_sector_weight,
                    )
                )

        return alerts
