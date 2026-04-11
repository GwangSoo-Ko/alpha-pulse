"""포트폴리오 이력 SQLite 저장소.

스냅샷, 주문, 거래, 성과 귀속을 portfolio.db에 저장한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class PortfolioStore:
    """포트폴리오 이력 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        """필요한 테이블을 모두 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    cash REAL,
                    total_value REAL,
                    positions TEXT,
                    daily_return REAL,
                    cumulative_return REAL,
                    drawdown REAL,
                    PRIMARY KEY (date, mode, run_id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    date TEXT,
                    stock_code TEXT,
                    stock_name TEXT,
                    side TEXT,
                    order_type TEXT,
                    quantity INTEGER,
                    price REAL,
                    strategy_id TEXT,
                    reason TEXT,
                    status TEXT,
                    filled_quantity INTEGER,
                    filled_price REAL,
                    commission REAL,
                    tax REAL,
                    created_at REAL,
                    filled_at REAL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    order_id TEXT,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    date TEXT,
                    stock_code TEXT,
                    side TEXT,
                    quantity INTEGER,
                    price REAL,
                    commission REAL,
                    tax REAL,
                    strategy_id TEXT,
                    realized_pnl REAL
                );

                CREATE TABLE IF NOT EXISTS attribution (
                    date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    strategy_returns TEXT,
                    factor_returns TEXT,
                    sector_returns TEXT,
                    PRIMARY KEY (date, mode, run_id)
                );

                CREATE TABLE IF NOT EXISTS strategy_rebalance (
                    strategy_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    last_rebalance_date TEXT NOT NULL,
                    updated_at REAL,
                    PRIMARY KEY (strategy_id, mode)
                );
                """
            )

    # ── Snapshots ─────────────────────────────────────────────────

    def save_snapshot(
        self,
        date: str,
        mode: str,
        cash: float,
        total_value: float,
        positions: list[dict],
        daily_return: float,
        cumulative_return: float,
        drawdown: float,
        run_id: str = "",
    ) -> None:
        """포트폴리오 스냅샷을 저장한다.

        Args:
            date: 날짜 (YYYYMMDD).
            mode: 실행 모드 ("backtest" | "paper" | "live").
            cash: 현금 (원).
            total_value: 총 자산 (원).
            positions: 포지션 리스트 (딕셔너리).
            daily_return: 일간 수익률 (%).
            cumulative_return: 누적 수익률 (%).
            drawdown: 드로다운 (%).
            run_id: 백테스트 실행 ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots
                    (date, mode, run_id, cash, total_value, positions,
                     daily_return, cumulative_return, drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date, mode, run_id, cash, total_value,
                    json.dumps(positions, ensure_ascii=False),
                    daily_return, cumulative_return, drawdown,
                ),
            )

    def get_snapshot(
        self, date: str, mode: str, run_id: str = ""
    ) -> dict | None:
        """특정 날짜 스냅샷을 조회한다.

        Args:
            date: 날짜 (YYYYMMDD).
            mode: 실행 모드.
            run_id: 백테스트 실행 ID.

        Returns:
            스냅샷 딕셔너리. 없으면 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM snapshots WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchone()
        return dict(row) if row else None

    def get_snapshots(
        self, start: str, end: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """기간별 스냅샷을 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
            mode: 실행 모드.
            run_id: 백테스트 실행 ID.

        Returns:
            스냅샷 딕셔너리 리스트 (날짜순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE date BETWEEN ? AND ? AND mode=? AND run_id=?
                ORDER BY date
                """,
                (start, end, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_snapshot(
        self, mode: str = "paper", run_id: str = ""
    ) -> dict | None:
        """지정 모드의 가장 최근 스냅샷을 반환한다.

        Args:
            mode: 실행 모드.
            run_id: 백테스트 실행 ID (backtest 모드 전용).

        Returns:
            최신 스냅샷 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE mode=? AND run_id=?
                ORDER BY date DESC
                LIMIT 1
                """,
                (mode, run_id),
            ).fetchone()
        return dict(row) if row else None

    def save_snapshot_obj(
        self,
        snapshot,
        mode: str,
        run_id: str = "",
    ) -> None:
        """PortfolioSnapshot 객체 형태로 스냅샷을 저장한다.

        Args:
            snapshot: PortfolioSnapshot 인스턴스.
            mode: 실행 모드.
            run_id: 백테스트 실행 ID.
        """
        positions_json = [
            {
                "code": p.stock.code,
                "name": p.stock.name,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "current_price": p.current_price,
                "weight": p.weight,
                "strategy_id": p.strategy_id,
            }
            for p in snapshot.positions
        ]
        self.save_snapshot(
            date=snapshot.date,
            mode=mode,
            cash=snapshot.cash,
            total_value=snapshot.total_value,
            positions=positions_json,
            daily_return=snapshot.daily_return,
            cumulative_return=snapshot.cumulative_return,
            drawdown=snapshot.drawdown,
            run_id=run_id,
        )

    # ── Orders ────────────────────────────────────────────────────

    def save_order(
        self,
        order_id: str,
        mode: str,
        date: str,
        stock_code: str,
        stock_name: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        strategy_id: str,
        reason: str,
        status: str,
        filled_quantity: int,
        filled_price: float,
        commission: float,
        tax: float,
        run_id: str = "",
    ) -> None:
        """주문을 저장한다."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders
                    (order_id, mode, run_id, date, stock_code, stock_name,
                     side, order_type, quantity, price, strategy_id, reason,
                     status, filled_quantity, filled_price, commission, tax,
                     created_at, filled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, mode, run_id, date, stock_code, stock_name,
                    side, order_type, quantity, price, strategy_id, reason,
                    status, filled_quantity, filled_price, commission, tax,
                    now, now if status == "filled" else None,
                ),
            )

    def get_orders(
        self, date: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """특정 날짜 주문을 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM orders WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Trades ────────────────────────────────────────────────────

    def save_trade(
        self,
        trade_id: str,
        order_id: str,
        mode: str,
        date: str,
        stock_code: str,
        side: str,
        quantity: int,
        price: float,
        commission: float,
        tax: float,
        strategy_id: str,
        realized_pnl: float,
        run_id: str = "",
    ) -> None:
        """거래를 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades
                    (trade_id, order_id, mode, run_id, date, stock_code,
                     side, quantity, price, commission, tax,
                     strategy_id, realized_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id, order_id, mode, run_id, date, stock_code,
                    side, quantity, price, commission, tax,
                    strategy_id, realized_pnl,
                ),
            )

    def get_trades(
        self, date: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """특정 날짜 거래를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Attribution ───────────────────────────────────────────────

    def save_attribution(
        self,
        date: str,
        mode: str,
        strategy_returns: dict,
        factor_returns: dict,
        sector_returns: dict,
        run_id: str = "",
    ) -> None:
        """성과 귀속을 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO attribution
                    (date, mode, run_id, strategy_returns,
                     factor_returns, sector_returns)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    date, mode, run_id,
                    json.dumps(strategy_returns, ensure_ascii=False),
                    json.dumps(factor_returns, ensure_ascii=False),
                    json.dumps(sector_returns, ensure_ascii=False),
                ),
            )

    def get_attribution(
        self, date: str, mode: str, run_id: str = ""
    ) -> dict | None:
        """성과 귀속을 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM attribution WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchone()
        return dict(row) if row else None

    # ── Strategy Rebalance Tracking ─────────────────────────────

    def get_last_rebalance(
        self, strategy_id: str, mode: str = "paper"
    ) -> str | None:
        """전략의 마지막 리밸런싱 날짜를 조회한다.

        Args:
            strategy_id: 전략 ID.
            mode: 실행 모드 (backtest/paper/live).

        Returns:
            YYYYMMDD 문자열 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT last_rebalance_date FROM strategy_rebalance "
                "WHERE strategy_id=? AND mode=?",
                (strategy_id, str(mode)),
            ).fetchone()
        return row[0] if row else None

    def set_last_rebalance(
        self, strategy_id: str, date: str, mode: str = "paper"
    ) -> None:
        """전략의 리밸런싱 날짜를 기록한다."""
        import time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO strategy_rebalance
                    (strategy_id, mode, last_rebalance_date, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (strategy_id, str(mode), date, time.time()),
            )
