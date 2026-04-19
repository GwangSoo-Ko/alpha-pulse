"""백테스트 결과 SQLite 저장소.

백테스트 실행 이력, 스냅샷을 backtest.db에 저장한다.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphapulse.trading.backtest.engine import BacktestResult


class BacktestStore:
    """백테스트 결과 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        """초기화.

        Args:
            db_path: 데이터베이스 파일 경로.
        """
        self.db_path = str(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        """필요한 테이블을 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    strategies TEXT DEFAULT '[]',
                    allocations TEXT DEFAULT '{}',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    final_value REAL NOT NULL,
                    benchmark TEXT DEFAULT 'KOSPI',
                    params TEXT DEFAULT '{}',
                    metrics TEXT DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    run_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    cash REAL,
                    total_value REAL,
                    daily_return REAL,
                    cumulative_return REAL,
                    drawdown REAL,
                    PRIMARY KEY (run_id, date),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS trades (
                    run_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    side TEXT NOT NULL,
                    quantity INTEGER,
                    price REAL,
                    commission REAL,
                    tax REAL,
                    strategy_id TEXT DEFAULT '',
                    trade_date TEXT DEFAULT '',
                    PRIMARY KEY (run_id, order_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS round_trips (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    buy_date TEXT,
                    buy_price REAL,
                    sell_date TEXT,
                    sell_price REAL,
                    quantity INTEGER,
                    pnl REAL,
                    return_pct REAL,
                    holding_days INTEGER,
                    commission REAL,
                    tax REAL,
                    strategy_id TEXT DEFAULT '',
                    PRIMARY KEY (run_id, seq),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def save_run(self, result: BacktestResult, name: str = "",
                 strategies: list[str] | None = None,
                 allocations: dict[str, float] | None = None) -> str:
        """백테스트 결과를 저장한다.

        Args:
            result: 백테스트 결과.
            name: 사용자 지정 이름 (선택).
            strategies: 전략 ID 목록 (선택).
            allocations: 전략별 배분 비율 (선택).

        Returns:
            생성된 run_id.
        """
        run_id = str(uuid.uuid4())
        config = result.config
        final_value = result.snapshots[-1].total_value if result.snapshots else config.initial_capital

        params = {
            "initial_capital": config.initial_capital,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "benchmark": config.benchmark,
            "use_ai": config.use_ai,
            "risk_free_rate": config.risk_free_rate,
        }

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, name, strategies, allocations,
                    start_date, end_date,
                    initial_capital, final_value, benchmark, params, metrics, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    name,
                    json.dumps(strategies or [], ensure_ascii=False),
                    json.dumps(allocations or {}, ensure_ascii=False),
                    config.start_date,
                    config.end_date,
                    config.initial_capital,
                    final_value,
                    config.benchmark,
                    json.dumps(params, ensure_ascii=False),
                    json.dumps(result.metrics, ensure_ascii=False),
                    time.time(),
                ),
            )

            # 스냅샷 저장
            snapshot_rows = [
                (
                    run_id,
                    s.date,
                    s.cash,
                    s.total_value,
                    s.daily_return,
                    s.cumulative_return,
                    s.drawdown,
                )
                for s in result.snapshots
            ]
            conn.executemany(
                """
                INSERT INTO snapshots (run_id, date, cash, total_value,
                    daily_return, cumulative_return, drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                snapshot_rows,
            )

            # 개별 체결 기록 저장
            trade_rows = [
                (
                    run_id,
                    t.order_id,
                    t.order.stock.code,
                    t.order.stock.name,
                    t.order.side,
                    t.filled_quantity,
                    t.filled_price,
                    t.commission,
                    t.tax,
                    t.order.strategy_id,
                    t.trade_date,
                )
                for t in result.trades
                if t.status == "filled"
            ]
            if trade_rows:
                conn.executemany(
                    """
                    INSERT INTO trades (run_id, order_id, code, name, side,
                        quantity, price, commission, tax, strategy_id,
                        trade_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    trade_rows,
                )

            # 라운드트립 저장
            from alphapulse.trading.backtest.metrics import build_round_trips
            rts = build_round_trips(result.trades)
            rt_rows = [
                (
                    run_id, i, rt["code"], rt["name"],
                    rt["buy_date"], rt["buy_price"],
                    rt["sell_date"], rt["sell_price"],
                    rt["quantity"], rt["pnl"], rt["return_pct"],
                    rt["holding_days"], rt["commission"], rt["tax"],
                    rt["strategy_id"],
                )
                for i, rt in enumerate(rts)
            ]
            if rt_rows:
                conn.executemany(
                    """
                    INSERT INTO round_trips (run_id, seq, code, name,
                        buy_date, buy_price, sell_date, sell_price,
                        quantity, pnl, return_pct, holding_days,
                        commission, tax, strategy_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rt_rows,
                )

        return run_id

    def get_run(self, run_id: str) -> dict | None:
        """실행 정보를 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            실행 정보 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_runs(self) -> list[dict]:
        """모든 실행 목록을 조회한다.

        Returns:
            실행 정보 딕셔너리 리스트 (최신순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_snapshots(self, run_id: str) -> list[dict]:
        """실행의 스냅샷 목록을 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            스냅샷 딕셔너리 리스트 (날짜순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE run_id = ? ORDER BY date",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trades(self, run_id: str) -> list[dict]:
        """실행의 개별 체결 기록을 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            체결 기록 딕셔너리 리스트 (날짜순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades WHERE run_id = ? ORDER BY trade_date, side",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_round_trips(self, run_id: str) -> list[dict]:
        """실행의 라운드트립(매수→매도 쌍)을 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            라운드트립 딕셔너리 리스트 (매수일순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM round_trips WHERE run_id = ? ORDER BY buy_date",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_run(self, run_id: str) -> None:
        """실행과 관련 데이터를 모두 삭제한다.

        Args:
            run_id: 실행 ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM round_trips WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM trades WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM snapshots WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
