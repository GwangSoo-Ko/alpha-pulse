"""종목 데이터 SQLite 저장소.

OHLCV, 재무제표, 수급, 공매도 데이터를 trading.db에 저장한다.
"""

import sqlite3
import time
from pathlib import Path


class TradingStore:
    """종목 데이터 저장소.

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
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    sector TEXT DEFAULT '',
                    market_cap REAL DEFAULT 0,
                    is_tradable INTEGER DEFAULT 1,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS ohlcv (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume INTEGER,
                    market_cap REAL DEFAULT 0,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS fundamentals (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    per REAL, pbr REAL, roe REAL,
                    revenue REAL, operating_profit REAL,
                    net_income REAL, debt_ratio REAL,
                    dividend_yield REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS stock_investor_flow (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    foreign_net REAL,
                    institutional_net REAL,
                    individual_net REAL,
                    foreign_holding_pct REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS short_interest (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    short_volume INTEGER,
                    short_balance INTEGER,
                    short_ratio REAL,
                    credit_balance REAL,
                    lending_balance REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS etf_info (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    category TEXT,
                    underlying TEXT,
                    expense_ratio REAL,
                    nav REAL,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS wisereport_data (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    -- 시장정보
                    market_cap REAL,
                    beta REAL,
                    foreign_pct REAL,
                    high_52w REAL,
                    low_52w REAL,
                    return_1m REAL,
                    return_3m REAL,
                    return_6m REAL,
                    return_1y REAL,
                    -- 주요지표 (실적)
                    per REAL, pbr REAL, pcr REAL,
                    ev_ebitda REAL,
                    eps REAL, bps REAL,
                    dividend_yield REAL,
                    -- 주요지표 (추정)
                    est_per REAL, est_eps REAL,
                    -- 컨센서스
                    target_price REAL,
                    analyst_count INTEGER,
                    consensus_opinion REAL,
                    -- 재무 (최근 연간)
                    revenue REAL,
                    operating_profit REAL,
                    net_income REAL,
                    roe REAL,
                    roa REAL,
                    debt_ratio REAL,
                    operating_margin REAL,
                    net_margin REAL,
                    PRIMARY KEY (code, date)
                );
                """
            )

    # ── Stocks ─────────────────────────────────────────────────────

    def upsert_stock(self, code: str, name: str, market: str,
                     sector: str = "", market_cap: float = 0) -> None:
        """종목 정보를 저장(upsert)한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO stocks (code, name, market, sector, market_cap, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name, market=excluded.market,
                    sector=excluded.sector, market_cap=excluded.market_cap,
                    updated_at=excluded.updated_at
                """,
                (code, name, market, sector, market_cap, time.time()),
            )

    def get_stock(self, code: str) -> dict | None:
        """종목 정보를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM stocks WHERE code = ?", (code,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_stocks(self, market: str | None = None) -> list[dict]:
        """전체 종목 목록을 조회한다."""
        query = "SELECT * FROM stocks WHERE is_tradable = 1"
        params: list = []
        if market:
            query += " AND market = ?"
            params.append(market)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── OHLCV ──────────────────────────────────────────────────────

    def save_ohlcv_bulk(self, rows: list[tuple]) -> None:
        """OHLCV 데이터를 대량 저장한다.

        Args:
            rows: (code, date, open, high, low, close, volume, market_cap) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv
                    (code, date, open, high, low, close, volume, market_cap)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_ohlcv(self, code: str, start: str, end: str) -> list[dict]:
        """OHLCV 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM ohlcv WHERE code = ? AND date BETWEEN ? AND ? ORDER BY date",
                (code, start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Fundamentals ───────────────────────────────────────────────

    def save_fundamental(self, code: str, date: str, **kwargs) -> None:
        """재무제표 데이터를 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fundamentals
                    (code, date, per, pbr, roe, revenue, operating_profit,
                     net_income, debt_ratio, dividend_yield)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, date,
                 kwargs.get("per"), kwargs.get("pbr"), kwargs.get("roe"),
                 kwargs.get("revenue"), kwargs.get("operating_profit"),
                 kwargs.get("net_income"), kwargs.get("debt_ratio"),
                 kwargs.get("dividend_yield")),
            )

    def get_fundamentals(self, code: str) -> dict | None:
        """가장 최근 재무제표를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM fundamentals WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    # ── Investor Flow ──────────────────────────────────────────────

    def save_investor_flow_bulk(self, rows: list[tuple]) -> None:
        """종목별 수급 데이터를 대량 저장한다.

        Args:
            rows: (code, date, foreign_net, institutional_net,
                   individual_net, foreign_holding_pct) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_investor_flow
                    (code, date, foreign_net, institutional_net,
                     individual_net, foreign_holding_pct)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_investor_flow(self, code: str, days: int = 20) -> list[dict]:
        """종목별 수급 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM stock_investor_flow "
                "WHERE code = ? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Short Interest ─────────────────────────────────────────────

    def save_short_interest_bulk(self, rows: list[tuple]) -> None:
        """공매도/신용 데이터를 대량 저장한다.

        Args:
            rows: (code, date, short_volume, short_balance,
                   short_ratio, credit_balance, lending_balance) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO short_interest
                    (code, date, short_volume, short_balance,
                     short_ratio, credit_balance, lending_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_short_interest(self, code: str, days: int = 20) -> list[dict]:
        """공매도/신용 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM short_interest "
                "WHERE code = ? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Wisereport ─────────────────────────────────────────────────

    _WISEREPORT_COLUMNS = (
        "market_cap", "beta", "foreign_pct", "high_52w", "low_52w",
        "return_1m", "return_3m", "return_6m", "return_1y",
        "per", "pbr", "pcr", "ev_ebitda", "eps", "bps", "dividend_yield",
        "est_per", "est_eps",
        "target_price", "analyst_count", "consensus_opinion",
        "revenue", "operating_profit", "net_income",
        "roe", "roa", "debt_ratio", "operating_margin", "net_margin",
    )

    def save_wisereport(self, code: str, date: str, **kwargs) -> None:
        """wisereport 데이터를 저장한다."""
        cols = ", ".join(self._WISEREPORT_COLUMNS)
        placeholders = ", ".join("?" for _ in self._WISEREPORT_COLUMNS)
        values = tuple(kwargs.get(c) for c in self._WISEREPORT_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO wisereport_data "
                f"(code, date, {cols}) VALUES (?, ?, {placeholders})",
                (code, date, *values),
            )

    def get_wisereport(self, code: str) -> dict | None:
        """가장 최근 wisereport 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wisereport_data "
                "WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None
