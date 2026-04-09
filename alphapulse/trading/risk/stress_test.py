"""시나리오 스트레스 테스트.

사전 정의된 위기 시나리오를 포트폴리오에 적용하여
예상 손실을 시뮬레이션한다.
"""

import logging
from dataclasses import dataclass, field

from alphapulse.trading.core.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


@dataclass
class StressResult:
    """스트레스 테스트 결과.

    Attributes:
        scenario_name: 시나리오 이름.
        description: 시나리오 설명.
        estimated_loss: 예상 손실 금액 (원, 음수).
        loss_pct: 예상 손실률 (%, 음수).
        contributions: 종목별 손실 기여 딕셔너리.
    """

    scenario_name: str
    description: str
    estimated_loss: float
    loss_pct: float
    contributions: dict[str, float] = field(default_factory=dict)


class StressTest:
    """시나리오별 포트폴리오 손실 시뮬레이션.

    사전 정의 시나리오 + 사용자 정의 시나리오를 지원한다.
    """

    SCENARIOS: dict[str, dict] = {
        "2020_covid": {
            "kospi": -0.35,
            "kosdaq": -0.40,
            "etf": -0.35,
            "desc": "COVID-19 급락 (2020.03)",
        },
        "2022_rate_hike": {
            "kospi": -0.25,
            "kosdaq": -0.35,
            "etf": -0.25,
            "desc": "금리 인상기 하락 (2022)",
        },
        "flash_crash": {
            "kospi": -0.10,
            "kosdaq": -0.15,
            "etf": -0.10,
            "desc": "일간 급락 (Flash Crash)",
        },
        "won_crisis": {
            "kospi": -0.20,
            "kosdaq": -0.25,
            "etf": -0.20,
            "desc": "원화 위기 + 외국인 이탈",
        },
        "sector_collapse": {
            "specific_sector": -0.50,
            "kospi": -0.10,
            "kosdaq": -0.15,
            "etf": -0.10,
            "desc": "특정 섹터 붕괴",
        },
    }

    def run(
        self,
        portfolio: PortfolioSnapshot,
        scenario: str,
    ) -> StressResult:
        """시나리오를 포트폴리오에 적용한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            scenario: 시나리오 이름.

        Returns:
            StressResult.

        Raises:
            KeyError: 미정의 시나리오.
        """
        if scenario not in self.SCENARIOS:
            raise KeyError(f"미정의 시나리오: {scenario}")

        shocks = self.SCENARIOS[scenario]
        desc = shocks.get("desc", scenario)

        total_loss = 0.0
        contributions: dict[str, float] = {}

        for pos in portfolio.positions:
            # 시장 유형에 따라 충격 적용
            market = pos.stock.market

            # 특정 섹터 붕괴 시나리오: 해당 섹터는 specific_sector 충격 적용
            if "specific_sector" in shocks and pos.stock.sector:
                shock = shocks.get("specific_sector", -0.50)
            elif market == "ETF":
                shock = shocks.get("etf", shocks.get("kospi", -0.10))
            elif market == "KOSDAQ":
                shock = shocks.get("kosdaq", shocks.get("kospi", -0.10))
            else:
                shock = shocks.get("kospi", -0.10)

            position_value = pos.quantity * pos.current_price
            position_loss = position_value * shock
            total_loss += position_loss
            contributions[pos.stock.code] = position_loss

        total_value = portfolio.total_value
        loss_pct = (total_loss / total_value * 100) if total_value > 0 else 0.0

        return StressResult(
            scenario_name=scenario,
            description=desc,
            estimated_loss=total_loss,
            loss_pct=loss_pct,
            contributions=contributions,
        )

    def run_all(
        self,
        portfolio: PortfolioSnapshot,
    ) -> dict[str, StressResult]:
        """전 시나리오를 일괄 실행한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            시나리오명 -> StressResult 매핑.
        """
        results = {}
        for name in self.SCENARIOS:
            results[name] = self.run(portfolio, name)
        return results

    def add_custom_scenario(self, name: str, shocks: dict) -> None:
        """사용자 정의 시나리오를 추가한다.

        Args:
            name: 시나리오 이름.
            shocks: 충격 파라미터 (kospi, kosdaq, etf, desc).
        """
        self.SCENARIOS[name] = shocks
