"""BacktestMetrics 테스트 — 성과 지표 계산."""

import numpy as np
import pytest

from alphapulse.trading.backtest.metrics import BacktestMetrics, build_round_trips
from alphapulse.trading.core.models import OrderResult, PortfolioSnapshot


@pytest.fixture
def metrics():
    return BacktestMetrics()


@pytest.fixture
def sample_snapshots():
    """20일치 스냅샷 — 초기 1억, 약간의 변동."""
    dates = [f"202604{d:02d}" for d in range(6, 30) if d not in (11, 12, 18, 19, 25, 26)]
    # 약 16 영업일
    values = [
        100_000_000,  # day 1
        100_500_000,  # +0.5%
        101_200_000,  # +0.7%
        100_800_000,  # -0.4%
        101_500_000,  # +0.7%
        102_000_000,  # +0.5%
        101_000_000,  # -1.0%
        100_000_000,  # -1.0%
        99_000_000,   # -1.0% (최대 낙폭 구간)
        100_200_000,  # +1.2%
        101_000_000,  # +0.8%
        102_500_000,  # +1.5%
        103_000_000,  # +0.5%
        103_500_000,  # +0.5%
        104_000_000,  # +0.5%
        104_500_000,  # +0.5%
    ]
    snapshots = []
    peak = values[0]
    for i, (date, value) in enumerate(zip(dates[:len(values)], values)):
        peak = max(peak, value)
        daily_ret = 0.0 if i == 0 else (value - values[i - 1]) / values[i - 1] * 100
        cum_ret = (value - values[0]) / values[0] * 100
        dd = (peak - value) / peak * 100
        snapshots.append(PortfolioSnapshot(
            date=date, cash=value * 0.1, positions=[],
            total_value=value, daily_return=daily_ret,
            cumulative_return=cum_ret, drawdown=-dd,
        ))
    return snapshots


@pytest.fixture
def benchmark_returns():
    """벤치마크 일간 수익률 (KOSPI)."""
    return np.array([
        0.003, 0.005, -0.002, 0.004, 0.003,
        -0.008, -0.005, -0.007, 0.010, 0.006,
        0.012, 0.004, 0.003, 0.002, 0.001,
    ])


@pytest.fixture
def sample_trades():
    """체결 이력 — 승패 혼합."""
    from alphapulse.trading.core.models import Order, Stock

    stock = Stock(code="005930", name="삼성전자", market="KOSPI")
    trades = []
    # 승리 거래 3건 (매수→매도 쌍으로 가정, 여기서는 매도 체결만)
    for price_pair in [(72000, 74000), (73000, 75000), (71000, 73500)]:
        buy_order = Order(stock=stock, side="BUY", order_type="MARKET",
                          quantity=100, price=None, strategy_id="test")
        sell_order = Order(stock=stock, side="SELL", order_type="MARKET",
                           quantity=100, price=None, strategy_id="test")
        trades.append(OrderResult(
            order_id="b1", order=buy_order, status="filled",
            filled_quantity=100, filled_price=price_pair[0],
            commission=108, tax=0, filled_at=None,
        ))
        trades.append(OrderResult(
            order_id="s1", order=sell_order, status="filled",
            filled_quantity=100, filled_price=price_pair[1],
            commission=111, tax=1332, filled_at=None,
        ))
    # 패배 거래 2건
    for price_pair in [(74000, 72000), (75000, 73000)]:
        buy_order = Order(stock=stock, side="BUY", order_type="MARKET",
                          quantity=100, price=None, strategy_id="test")
        sell_order = Order(stock=stock, side="SELL", order_type="MARKET",
                           quantity=100, price=None, strategy_id="test")
        trades.append(OrderResult(
            order_id="b2", order=buy_order, status="filled",
            filled_quantity=100, filled_price=price_pair[0],
            commission=111, tax=0, filled_at=None,
        ))
        trades.append(OrderResult(
            order_id="s2", order=sell_order, status="filled",
            filled_quantity=100, filled_price=price_pair[1],
            commission=108, tax=1296, filled_at=None,
        ))
    return trades


class TestReturnMetrics:
    def test_total_return(self, metrics, sample_snapshots):
        """총 수익률이 올바르게 계산된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["total_return"] == pytest.approx(4.5, abs=0.1)

    def test_cagr(self, metrics, sample_snapshots):
        """CAGR이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["cagr"] > 0


class TestMonthlyReturns:
    def test_monthly_returns_is_list(self, metrics, sample_snapshots):
        """monthly_returns가 리스트로 반환된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert "monthly_returns" in result
        assert isinstance(result["monthly_returns"], list)

    def test_monthly_returns_empty_on_single_snapshot(self, metrics):
        """스냅샷 1개 → monthly_returns 빈 리스트."""
        snap = PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        result = metrics.calculate([snap], np.array([0.0]))
        assert result["monthly_returns"] == []


class TestRiskMetrics:
    def test_max_drawdown(self, metrics, sample_snapshots):
        """최대 낙폭(MDD)이 계산된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["max_drawdown"] < 0

    def test_max_drawdown_duration(self, metrics, sample_snapshots):
        """MDD 지속 기간이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["max_drawdown_duration"] >= 1

    def test_volatility(self, metrics, sample_snapshots):
        """변동성이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["volatility"] > 0


class TestRiskAdjusted:
    def test_sharpe_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """샤프 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "sharpe_ratio" in result
        assert isinstance(result["sharpe_ratio"], float)

    def test_sortino_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """소르티노 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "sortino_ratio" in result

    def test_calmar_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """칼마 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "calmar_ratio" in result


class TestTradeMetrics:
    def test_win_rate(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """승률이 올바르게 계산된다."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        # 3승 2패 → 60%
        assert result["win_rate"] == pytest.approx(60.0, abs=1.0)

    def test_profit_factor(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """이익 팩터가 1 이상이다 (순이익)."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        assert result["profit_factor"] > 1.0

    def test_total_trades(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """총 체결 건수와 라운드트립이 올바르다."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        # 매수 5 + 매도 5 = 10건 체결, 5 라운드트립
        assert result["total_orders"] == 10
        assert result["round_trips"] == 5
        assert result["total_trades"] == 10  # total_orders와 동일


class TestBenchmarkMetrics:
    def test_benchmark_return(self, metrics, sample_snapshots, benchmark_returns):
        """벤치마크 수익률이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "benchmark_return" in result

    def test_alpha(self, metrics, sample_snapshots, benchmark_returns):
        """알파가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "alpha" in result

    def test_beta(self, metrics, sample_snapshots, benchmark_returns):
        """베타가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "beta" in result

    def test_information_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """정보 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "information_ratio" in result

    def test_tracking_error(self, metrics, sample_snapshots, benchmark_returns):
        """추적 오차가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "tracking_error" in result
        assert result["tracking_error"] >= 0


class TestEdgeCases:
    def test_single_snapshot(self, metrics):
        """스냅샷 1개 → 최소 결과 반환."""
        snap = PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        result = metrics.calculate([snap], np.array([0.0]))
        assert result["total_return"] == 0.0
        assert result["sharpe_ratio"] == 0.0

    def test_empty_trades(self, metrics, sample_snapshots, benchmark_returns):
        """거래 없음 → 승률 0, profit_factor 0."""
        result = metrics.calculate(sample_snapshots, benchmark_returns, trades=[])
        assert result["win_rate"] == 0.0
        assert result["profit_factor"] == 0.0
        assert result["total_trades"] == 0


class TestBuildRoundTrips:
    """build_round_trips 상세 라운드트립 테스트."""

    def test_round_trip_count(self, sample_trades):
        """5개 라운드트립이 생성된다 (3승 2패)."""
        rts = build_round_trips(sample_trades)
        assert len(rts) == 5

    def test_round_trip_fields(self, sample_trades):
        """라운드트립에 필수 필드가 모두 있다."""
        rts = build_round_trips(sample_trades)
        required = {
            "code", "name", "buy_date", "buy_price",
            "sell_date", "sell_price", "quantity",
            "pnl", "return_pct", "holding_days",
            "commission", "tax", "strategy_id",
        }
        for rt in rts:
            assert required.issubset(rt.keys())

    def test_winning_trade_positive_pnl(self, sample_trades):
        """승리 거래는 양의 PnL을 가진다."""
        rts = build_round_trips(sample_trades)
        first = rts[0]  # 72000 → 74000
        assert first["pnl"] > 0
        assert first["return_pct"] > 0

    def test_losing_trade_negative_pnl(self, sample_trades):
        """패배 거래는 음의 PnL을 가진다."""
        rts = build_round_trips(sample_trades)
        losers = [r for r in rts if r["pnl"] < 0]
        assert len(losers) == 2

    def test_trade_date_recorded(self):
        """trade_date가 있으면 보유기간이 계산된다."""
        from alphapulse.trading.core.models import Order, Stock

        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        buy_order = Order(stock=stock, side="BUY", order_type="MARKET",
                          quantity=10, price=None, strategy_id="test")
        sell_order = Order(stock=stock, side="SELL", order_type="MARKET",
                           quantity=10, price=None, strategy_id="test")
        trades = [
            OrderResult(
                order_id="b1", order=buy_order, status="filled",
                filled_quantity=10, filled_price=50000,
                commission=7, tax=0, trade_date="20260101",
            ),
            OrderResult(
                order_id="s1", order=sell_order, status="filled",
                filled_quantity=10, filled_price=55000,
                commission=8, tax=990, trade_date="20260115",
            ),
        ]
        rts = build_round_trips(trades)
        assert len(rts) == 1
        assert rts[0]["holding_days"] == 14
        assert rts[0]["buy_date"] == "20260101"
        assert rts[0]["sell_date"] == "20260115"

    def test_empty_trades(self):
        """빈 거래 목록 → 빈 라운드트립."""
        assert build_round_trips([]) == []
