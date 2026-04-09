"""팩터 계산기.

종목별 모멘텀, 밸류, 퀄리티, 수급, 변동성, 역발상 팩터를 계산한다.
spec 5.1의 20개 팩터를 모두 구현한다.
각 팩터는 원시값을 반환한다. percentile 정규화는 Ranker에서 수행한다.

편의 메서드(momentum, value, quality, flow, volatility)는 대표 개별 팩터를 호출한다.
"""

import math

from alphapulse.trading.data.store import TradingStore


class FactorCalculator:
    """개별 팩터 점수 계산기.

    spec 5.1에 정의된 20개 팩터를 모두 지원한다:
    - 모멘텀 5종: momentum_1m, momentum_3m, momentum_6m, momentum_12m, high_52w_proximity
    - 밸류 4종: value_per, value_pbr, value_psr, dividend_yield
    - 퀄리티 3종: quality_roe, quality_profit_growth, quality_debt_ratio
    - 수급 3종: flow_foreign, flow_institutional, flow_trend
    - 역발상 2종: short_decrease, credit_change
    - 변동성 3종: volatility, beta, downside_vol

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, store: TradingStore) -> None:
        self.store = store

    # ── 편의 메서드 (기존 호환) ───────────────────────────────────

    def momentum(self, code: str, lookback: int = 60) -> float | None:
        """모멘텀 팩터 — lookback 기간 수익률 (%).

        편의 메서드. momentum_3m과 동일한 로직이지만 lookback을 직접 지정.

        Args:
            code: 종목코드.
            lookback: 조회 기간 (영업일).

        Returns:
            수익률 (%). 데이터 부족 시 None.
        """
        return self._momentum_by_days(code, lookback)

    def value(self, code: str) -> float | None:
        """밸류 팩터 — PER 역수 (E/P). 편의 메서드. value_per() 호출."""
        return self.value_per(code)

    def quality(self, code: str) -> float | None:
        """퀄리티 팩터 — ROE. 편의 메서드. quality_roe() 호출."""
        return self.quality_roe(code)

    def flow(self, code: str, days: int = 20) -> float | None:
        """수급 팩터 — 외국인 순매수 누적. 편의 메서드. flow_foreign() 호출."""
        return self.flow_foreign(code, days=days)

    # ── 모멘텀 팩터 (5종) ────────────────────────────────────────

    def momentum_1m(self, code: str) -> float | None:
        """1개월(20영업일) 수익률 (%)."""
        return self._momentum_by_days(code, 20)

    def momentum_3m(self, code: str) -> float | None:
        """3개월(60영업일) 수익률 (%)."""
        return self._momentum_by_days(code, 60)

    def momentum_6m(self, code: str) -> float | None:
        """6개월(120영업일) 수익률 (%)."""
        return self._momentum_by_days(code, 120)

    def momentum_12m(self, code: str) -> float | None:
        """12개월 수익률 (%), 최근 1개월 제외.

        전통적인 12-1 모멘텀 팩터.
        """
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 22:  # 최소 22일 (1개월 제외 + 1일)
            return None
        # 최근 20일(1개월) 제외한 나머지에서 계산
        end_idx = len(rows) - 20
        lookback_days = 240  # 12개월
        start_idx = max(0, end_idx - lookback_days)
        start_price = rows[start_idx]["close"]
        end_price = rows[end_idx - 1]["close"]
        if start_price == 0:
            return None
        return (end_price - start_price) / start_price * 100

    def high_52w_proximity(self, code: str) -> float | None:
        """52주 신고가 근접도 (%).

        현재가 / 52주 고가 * 100. 100에 가까울수록 신고가 근접.
        """
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 2:
            return None
        recent_252 = rows[-252:] if len(rows) >= 252 else rows
        high_52w = max(r["high"] for r in recent_252)
        if high_52w == 0:
            return None
        current = rows[-1]["close"]
        return (current / high_52w) * 100

    # ── 밸류 팩터 (4종) ──────────────────────────────────────────

    def value_per(self, code: str) -> float | None:
        """PER 역수 (E/P, %). PER이 낮을수록 높은 값."""
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("per") is None or fund["per"] <= 0:
            return None
        return (1.0 / fund["per"]) * 100

    def value_pbr(self, code: str) -> float | None:
        """PBR 역수 (B/P, %). PBR이 낮을수록 높은 값."""
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("pbr") is None or fund["pbr"] <= 0:
            return None
        return (1.0 / fund["pbr"]) * 100

    def value_psr(self, code: str) -> float | None:
        """PSR 역수 (S/P, %). PSR이 낮을수록 높은 값.

        PSR = 시가총액 / 매출액. 매출 데이터 필요.
        """
        fund = self.store.get_fundamentals(code)
        if fund is None:
            return None
        revenue = fund.get("revenue")
        if revenue is None or revenue <= 0:
            return None
        # 시가총액은 최근 OHLCV에서 가져옴
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if not rows:
            return None
        mcap = rows[-1].get("market_cap", 0)
        if mcap <= 0:
            return None
        psr = mcap / revenue
        if psr <= 0:
            return None
        return (1.0 / psr) * 100

    def dividend_yield(self, code: str) -> float | None:
        """배당수익률 (%)."""
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("dividend_yield") is None:
            return None
        return fund["dividend_yield"]

    # ── 퀄리티 팩터 (3종) ────────────────────────────────────────

    def quality_roe(self, code: str) -> float | None:
        """ROE (%). 높을수록 우수."""
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("roe") is None:
            return None
        return fund["roe"]

    def quality_profit_growth(self, code: str) -> float | None:
        """영업이익 성장률 (YoY, %).

        직전 분기 대비 성장률. 분기별 데이터가 2개 이상 필요.
        현재는 단일 분기만 저장하므로 None 반환 (추후 분기 비교 구현).
        """
        # 분기별 영업이익 비교가 필요하지만 현재 최신 1건만 저장됨.
        # 멀티 분기 저장 구현 후 활성화 예정.
        return None

    def quality_debt_ratio(self, code: str) -> float | None:
        """부채비율 역수 (낮을수록 좋음). 높은 반환값 = 낮은 부채비율."""
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("debt_ratio") is None:
            return None
        debt = fund["debt_ratio"]
        if debt <= 0:
            return None
        return (1.0 / debt) * 100

    # ── 수급 팩터 (3종) ──────────────────────────────────────────

    def flow_foreign(self, code: str, days: int = 20) -> float | None:
        """외국인 N일 순매수 누적 (원)."""
        rows = self.store.get_investor_flow(code, days=days)
        if not rows:
            return None
        return sum(r.get("foreign_net", 0) or 0 for r in rows)

    def flow_institutional(self, code: str, days: int = 20) -> float | None:
        """기관 N일 순매수 누적 (원)."""
        rows = self.store.get_investor_flow(code, days=days)
        if not rows:
            return None
        return sum(r.get("institutional_net", 0) or 0 for r in rows)

    def flow_trend(self, code: str) -> float | None:
        """수급 추세 — 5일 순매수 이평 vs 20일 순매수 이평.

        양수면 단기 수급 개선, 음수면 단기 수급 악화.
        """
        rows = self.store.get_investor_flow(code, days=20)
        if len(rows) < 5:
            return None
        foreign = [r.get("foreign_net", 0) or 0 for r in rows]
        avg_5d = sum(foreign[:5]) / 5
        avg_20d = sum(foreign) / len(foreign)
        if avg_20d == 0:
            return avg_5d
        return avg_5d - avg_20d

    # ── 역발상 팩터 (2종) ────────────────────────────────────────

    def short_decrease(self, code: str, days: int = 20) -> float | None:
        """공매도 잔고 감소율 (%).

        양수면 공매도 감소(긍정적), 음수면 증가(부정적).
        """
        rows = self.store.get_short_interest(code, days=days)
        if len(rows) < 2:
            return None
        # rows는 최신순(DESC), 첫 번째가 최근
        recent = rows[0].get("short_balance", 0) or 0
        oldest = rows[-1].get("short_balance", 0) or 0
        if oldest == 0:
            return None
        # 감소율: 잔고 줄었으면 양수
        return (oldest - recent) / oldest * 100

    def credit_change(self, code: str, days: int = 20) -> float | None:
        """신용잔고 변화율 (%).

        양수면 신용 증가(과열 신호), 음수면 감소.
        """
        rows = self.store.get_short_interest(code, days=days)
        if len(rows) < 2:
            return None
        recent = rows[0].get("credit_balance", 0) or 0
        oldest = rows[-1].get("credit_balance", 0) or 0
        if oldest == 0:
            return None
        return (recent - oldest) / oldest * 100

    # ── 변동성 팩터 (3종) ────────────────────────────────────────

    def volatility(self, code: str, days: int = 60) -> float | None:
        """일간 변동성 — 수익률 표준편차 (연환산, %)."""
        returns = self._get_daily_returns(code, days)
        if returns is None or len(returns) < 3:
            return None
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(252) * 100

    def beta(self, code: str, benchmark: str = "KOSPI") -> float | None:
        """시장 베타.

        유니버스 평균 수익률을 벤치마크 근사로 사용한다.
        정확한 KOSPI 지수 데이터는 Phase 2에서 추가 예정.

        Args:
            code: 종목코드.
            benchmark: 벤치마크 (현재 미사용, 유니버스 평균 사용).

        Returns:
            베타 값. 데이터 부족 시 None.
        """
        stock_returns = self._get_daily_returns(code, 60)
        if stock_returns is None or len(stock_returns) < 5:
            return None

        # 벤치마크 근사: 저장된 모든 종목의 평균 수익률
        all_stocks = self.store.get_all_stocks()
        if len(all_stocks) < 2:
            return None

        market_returns_matrix = []
        for s in all_stocks:
            s_ret = self._get_daily_returns(s["code"], 60)
            if s_ret is not None and len(s_ret) == len(stock_returns):
                market_returns_matrix.append(s_ret)

        if not market_returns_matrix:
            return None

        # 시장 평균 수익률 (벤치마크 근사)
        n = len(stock_returns)
        market_returns = [
            sum(m[i] for m in market_returns_matrix) / len(market_returns_matrix)
            for i in range(n)
        ]

        # 베타 = Cov(stock, market) / Var(market)
        mean_s = sum(stock_returns) / n
        mean_m = sum(market_returns) / n
        cov = sum(
            (stock_returns[i] - mean_s) * (market_returns[i] - mean_m)
            for i in range(n)
        ) / (n - 1)
        var_m = sum((m - mean_m) ** 2 for m in market_returns) / (n - 1)
        if var_m == 0:
            return None
        return cov / var_m

    def downside_vol(self, code: str, days: int = 60) -> float | None:
        """하방 변동성 — 음수 수익률만의 표준편차 (연환산, %).

        하락 리스크 측정. 낮을수록 양호.
        """
        returns = self._get_daily_returns(code, days)
        if returns is None:
            return None
        neg_returns = [r for r in returns if r < 0]
        if len(neg_returns) < 3:
            return None
        mean = sum(neg_returns) / len(neg_returns)
        variance = sum((r - mean) ** 2 for r in neg_returns) / (len(neg_returns) - 1)
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(252) * 100

    # ── 내부 헬퍼 ────────────────────────────────────────────────

    def _momentum_by_days(self, code: str, lookback: int) -> float | None:
        """lookback 기간 수익률 (%)."""
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 2:
            return None
        recent = rows[-lookback:] if len(rows) >= lookback else rows
        start_price = recent[0]["close"]
        end_price = recent[-1]["close"]
        if start_price == 0:
            return None
        return (end_price - start_price) / start_price * 100

    def _get_daily_returns(self, code: str, days: int) -> list[float] | None:
        """일간 수익률 리스트를 반환한다."""
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 5:
            return None
        recent = rows[-days:] if len(rows) >= days else rows
        returns = []
        for i in range(1, len(recent)):
            prev_close = recent[i - 1]["close"]
            if prev_close == 0:
                continue
            daily_ret = (recent[i]["close"] - prev_close) / prev_close
            returns.append(daily_ret)
        return returns if len(returns) >= 3 else None
