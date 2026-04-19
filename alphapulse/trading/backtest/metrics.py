"""백테스트 성과 지표 계산.

수익률, 리스크, 거래 분석, 벤치마크 비교 지표를 모두 계산한다.
"""

import numpy as np

from alphapulse.trading.core.models import OrderResult, PortfolioSnapshot


class BacktestMetrics:
    """백테스트 결과 분석.

    스냅샷 목록, 벤치마크 수익률, 체결 이력을 입력받아
    포괄적 성과 지표를 계산한다.
    """

    def calculate(
        self,
        snapshots: list[PortfolioSnapshot],
        benchmark_returns: np.ndarray,
        risk_free_rate: float = 0.035,
        trades: list[OrderResult] | None = None,
    ) -> dict:
        """성과 지표를 계산한다.

        Args:
            snapshots: 일별 포트폴리오 스냅샷 목록.
            benchmark_returns: 벤치마크 일간 수익률 배열.
            risk_free_rate: 무위험 이자율 (연율, 기본 3.5%).
            trades: 체결 이력 (없으면 거래 지표 0).

        Returns:
            모든 성과 지표를 담은 딕셔너리.
        """
        if len(snapshots) <= 1:
            return self._empty_metrics()

        values = np.array([s.total_value for s in snapshots])
        dates = [s.date for s in snapshots]
        daily_returns = np.diff(values) / values[:-1]
        n_days = len(daily_returns)
        annualization = 252

        # 월별 수익률 — 일간 수익률을 월 단위로 복리 계산
        monthly_returns = self._calculate_monthly_returns(dates, daily_returns)

        # 수익률
        total_return = (values[-1] - values[0]) / values[0] * 100
        years = n_days / annualization
        cagr = ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years > 0 else 0.0

        # 리스크
        volatility = float(np.std(daily_returns, ddof=1) * np.sqrt(annualization) * 100)
        mdd, mdd_duration = self._max_drawdown(values)
        downside_returns = daily_returns[daily_returns < 0]
        downside_dev = (
            float(np.std(downside_returns, ddof=1) * np.sqrt(annualization) * 100)
            if len(downside_returns) > 1
            else 0.0
        )

        # 리스크 조정 수익
        daily_rf = risk_free_rate / annualization
        excess_daily = daily_returns - daily_rf
        sharpe = (
            float(
                np.mean(excess_daily)
                / np.std(excess_daily, ddof=1)
                * np.sqrt(annualization)
            )
            if np.std(excess_daily, ddof=1) > 0
            else 0.0
        )
        sortino = (
            float(
                np.mean(excess_daily)
                / (np.std(downside_returns, ddof=1))
                * np.sqrt(annualization)
            )
            if len(downside_returns) > 1 and np.std(downside_returns, ddof=1) > 0
            else 0.0
        )
        calmar = cagr / abs(mdd) if mdd != 0 else 0.0

        # 거래 분석
        trade_metrics = self._calculate_trade_metrics(trades or [], values[0])

        # 벤치마크 비교
        bench_metrics = self._calculate_benchmark_metrics(
            daily_returns,
            benchmark_returns[:n_days],
            risk_free_rate,
            annualization,
        )

        return {
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "monthly_returns": monthly_returns,
            "volatility": round(volatility, 4),
            "max_drawdown": round(mdd, 4),
            "max_drawdown_duration": mdd_duration,
            "downside_deviation": round(downside_dev, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            **trade_metrics,
            **bench_metrics,
        }

    def _max_drawdown(self, values: np.ndarray) -> tuple[float, int]:
        """최대 낙폭(MDD)과 지속 기간을 계산한다.

        Returns:
            (MDD 비율 (음수, %), 지속 기간 (영업일)).
        """
        peak = values[0]
        max_dd = 0.0
        max_duration = 0
        current_duration = 0

        for i in range(len(values)):
            if values[i] > peak:
                peak = values[i]
                current_duration = 0
            else:
                dd = (peak - values[i]) / peak
                current_duration += 1
                if dd > max_dd:
                    max_dd = dd
                    max_duration = current_duration

        return -round(max_dd * 100, 4), max(max_duration, 0)

    @staticmethod
    def _calculate_monthly_returns(
        dates: list[str],
        daily_returns: np.ndarray,
    ) -> list[float]:
        """일간 수익률을 월별로 그룹화하여 복리 수익률을 계산한다.

        Args:
            dates: 스냅샷 날짜 리스트 (YYYYMMDD). daily_returns보다 1개 더 많음.
            daily_returns: 일간 수익률 배열.

        Returns:
            월별 복리 수익률 리스트 (%).
        """
        if len(daily_returns) == 0:
            return []

        # 월(YYYYMM) 기준으로 일간 수익률 그룹화 (dates[1:]과 daily_returns 대응)
        monthly: dict[str, list[float]] = {}
        for i, ret in enumerate(daily_returns):
            month_key = dates[i + 1][:6]  # YYYYMM
            monthly.setdefault(month_key, []).append(float(ret))

        # 월별 복리 수익률
        result = []
        for month_key in sorted(monthly.keys()):
            compound = float(np.prod([1 + r for r in monthly[month_key]]) - 1) * 100
            result.append(round(compound, 4))

        return result

    def _calculate_trade_metrics(
        self, trades: list[OrderResult], initial_capital: float
    ) -> dict:
        """거래 분석 지표를 계산한다.

        전체 체결 건수와 매수-매도 라운드트립을 모두 추적한다.
        """
        if not trades:
            return {
                "total_orders": 0,
                "filled_buys": 0,
                "filled_sells": 0,
                "round_trips": 0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "turnover": 0.0,
            }

        # 종목별 매수→매도 쌍으로 라운드트립 추출
        buys: dict[str, list[OrderResult]] = {}
        round_trips: list[float] = []
        total_traded_amount = 0.0
        filled_buys = 0
        filled_sells = 0

        for trade in trades:
            if trade.status != "filled":
                continue
            code = trade.order.stock.code
            total_traded_amount += trade.filled_quantity * trade.filled_price

            if trade.order.side == "BUY":
                buys.setdefault(code, []).append(trade)
                filled_buys += 1
            else:  # SELL
                filled_sells += 1
                if code in buys and buys[code]:
                    buy_trade = buys[code].pop(0)
                    pnl = (
                        trade.filled_price - buy_trade.filled_price
                    ) * trade.filled_quantity
                    pnl -= trade.commission + trade.tax + buy_trade.commission
                    round_trips.append(pnl)

        total_orders = filled_buys + filled_sells
        n_round_trips = len(round_trips)

        wins = [pnl for pnl in round_trips if pnl > 0]
        losses = [pnl for pnl in round_trips if pnl <= 0]

        win_rate = len(wins) / n_round_trips * 100 if n_round_trips > 0 else 0.0
        total_profit = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        avg_win = (total_profit / len(wins)) if wins else 0.0
        avg_loss = (total_loss / len(losses)) if losses else 0.0

        turnover = total_traded_amount / initial_capital if initial_capital > 0 else 0.0

        return {
            "total_orders": total_orders,
            "filled_buys": filled_buys,
            "filled_sells": filled_sells,
            "round_trips": n_round_trips,
            "total_trades": total_orders,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "turnover": round(turnover, 4),
        }

    def _calculate_benchmark_metrics(
        self,
        portfolio_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        risk_free_rate: float,
        annualization: int,
    ) -> dict:
        """벤치마크 비교 지표를 계산한다."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 2:
            return {
                "benchmark_return": 0.0,
                "excess_return": 0.0,
                "beta": 0.0,
                "alpha": 0.0,
                "information_ratio": 0.0,
                "tracking_error": 0.0,
            }

        pr = portfolio_returns[:n]
        br = benchmark_returns[:n]

        benchmark_total = float(np.prod(1 + br) - 1) * 100
        portfolio_total = float(np.prod(1 + pr) - 1) * 100
        excess = portfolio_total - benchmark_total

        # 베타 = Cov(Rp, Rb) / Var(Rb)
        cov_matrix = np.cov(pr, br)
        beta = (
            float(cov_matrix[0, 1] / cov_matrix[1, 1])
            if cov_matrix[1, 1] > 0
            else 0.0
        )

        # 알파 (젠센 알파) = Rp - [Rf + beta * (Rb - Rf)]
        daily_rf = risk_free_rate / annualization
        alpha = (
            float(np.mean(pr) - (daily_rf + beta * (np.mean(br) - daily_rf)))
            * annualization
            * 100
        )

        # 추적 오차
        active_returns = pr - br
        tracking_error = float(
            np.std(active_returns, ddof=1) * np.sqrt(annualization) * 100
        )

        # 정보 비율
        information_ratio = (
            float(
                np.mean(active_returns)
                / np.std(active_returns, ddof=1)
                * np.sqrt(annualization)
            )
            if np.std(active_returns, ddof=1) > 0
            else 0.0
        )

        return {
            "benchmark_return": round(benchmark_total, 4),
            "excess_return": round(excess, 4),
            "beta": round(beta, 4),
            "alpha": round(alpha, 4),
            "information_ratio": round(information_ratio, 4),
            "tracking_error": round(tracking_error, 4),
        }

    @staticmethod
    def _empty_metrics() -> dict:
        """스냅샷 부족 시 빈 지표를 반환한다."""
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "monthly_returns": [],
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "downside_deviation": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "total_orders": 0,
            "filled_buys": 0,
            "filled_sells": 0,
            "round_trips": 0,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "turnover": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "beta": 0.0,
            "alpha": 0.0,
            "information_ratio": 0.0,
            "tracking_error": 0.0,
        }


def build_round_trips(trades: list[OrderResult]) -> list[dict]:
    """체결 이력에서 상세 라운드트립(매수→매도 쌍) 목록을 생성한다.

    FIFO 방식으로 매수-매도를 매칭하고, 보유기간·수익률·손익을 계산한다.

    Args:
        trades: 시간순 체결 이력.

    Returns:
        라운드트립 딕셔너리 리스트.
    """
    buys: dict[str, list[OrderResult]] = {}
    result: list[dict] = []

    for trade in trades:
        if trade.status != "filled":
            continue
        code = trade.order.stock.code

        if trade.order.side == "BUY":
            buys.setdefault(code, []).append(trade)
        else:
            if code not in buys or not buys[code]:
                continue
            buy = buys[code].pop(0)
            qty = min(trade.filled_quantity, buy.filled_quantity)
            cost = buy.filled_price * qty
            revenue = trade.filled_price * qty
            total_fees = (
                buy.commission + trade.commission + trade.tax
            )
            pnl = revenue - cost - total_fees
            return_pct = (pnl / cost * 100) if cost > 0 else 0.0

            buy_date = buy.trade_date or ""
            sell_date = trade.trade_date or ""
            holding_days = _calc_holding_days(buy_date, sell_date)

            result.append({
                "code": code,
                "name": trade.order.stock.name,
                "buy_date": buy_date,
                "buy_price": round(buy.filled_price, 2),
                "sell_date": sell_date,
                "sell_price": round(trade.filled_price, 2),
                "quantity": qty,
                "pnl": round(pnl, 2),
                "return_pct": round(return_pct, 2),
                "holding_days": holding_days,
                "commission": round(buy.commission + trade.commission, 2),
                "tax": round(trade.tax, 2),
                "strategy_id": trade.order.strategy_id,
            })

    return result


def _calc_holding_days(buy_date: str, sell_date: str) -> int:
    """두 날짜 사이의 캘린더 일수를 계산한다."""
    if not buy_date or not sell_date or len(buy_date) != 8:
        return 0
    try:
        from datetime import datetime
        b = datetime.strptime(buy_date, "%Y%m%d")
        s = datetime.strptime(sell_date, "%Y%m%d")
        return (s - b).days
    except ValueError:
        return 0
