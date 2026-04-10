"""종목 데이터 SQLite 저장소.

OHLCV, 재무제표, 수급, 공매도, wisereport 전체 탭 데이터를 trading.db에 저장한다.
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

                -- 기업개요 (c1020001)
                CREATE TABLE IF NOT EXISTS company_overview (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    products TEXT,
                    rd_expense REAL,
                    rd_ratio REAL,
                    established TEXT,
                    listed TEXT,
                    employees INTEGER,
                    subsidiary_count INTEGER,
                    PRIMARY KEY (code, date)
                );

                -- 투자지표 시계열 (c1040001)
                CREATE TABLE IF NOT EXISTS investment_indicators (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    period TEXT NOT NULL,
                    indicator TEXT NOT NULL,
                    value REAL,
                    PRIMARY KEY (code, date, period, indicator)
                );

                -- 컨센서스 추정실적 (c1050001)
                CREATE TABLE IF NOT EXISTS consensus_estimates (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    period TEXT NOT NULL,
                    revenue REAL,
                    operating_profit REAL,
                    net_income REAL,
                    eps REAL,
                    per REAL,
                    analyst_count INTEGER,
                    PRIMARY KEY (code, date, period)
                );

                -- 업종 비교 (c1060001)
                CREATE TABLE IF NOT EXISTS sector_comparison (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    sector TEXT,
                    rank_in_sector INTEGER,
                    sector_per REAL,
                    sector_pbr REAL,
                    comparison_data TEXT,
                    PRIMARY KEY (code, date)
                );

                -- 지분 현황 (c1070001)
                CREATE TABLE IF NOT EXISTS shareholder_data (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    largest_holder TEXT,
                    largest_pct REAL,
                    foreign_pct REAL,
                    institutional_pct REAL,
                    float_pct REAL,
                    float_shares INTEGER,
                    changes TEXT,
                    PRIMARY KEY (code, date)
                );

                -- 증권사 리포트 (c1080001)
                CREATE TABLE IF NOT EXISTS analyst_reports (
                    code TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    analyst TEXT,
                    provider TEXT,
                    title TEXT,
                    opinion TEXT,
                    target_price REAL,
                    PRIMARY KEY (code, report_date, provider)
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

    # ── Company Overview (c1020001) ───────────────────────────────

    _OVERVIEW_COLUMNS = (
        "products", "rd_expense", "rd_ratio",
        "established", "listed", "employees", "subsidiary_count",
    )

    def save_company_overview(self, code: str, date: str, **kwargs) -> None:
        """기업개요 데이터를 저장한다."""
        cols = ", ".join(self._OVERVIEW_COLUMNS)
        placeholders = ", ".join("?" for _ in self._OVERVIEW_COLUMNS)
        values = tuple(kwargs.get(c) for c in self._OVERVIEW_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO company_overview "
                f"(code, date, {cols}) VALUES (?, ?, {placeholders})",
                (code, date, *values),
            )

    def get_company_overview(self, code: str) -> dict | None:
        """가장 최근 기업개요 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM company_overview "
                "WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    # ── Investment Indicators (c1040001) ──────────────────────────

    def save_investment_indicators(
        self, code: str, date: str, rows: list[tuple],
    ) -> None:
        """투자지표 시계열을 저장한다.

        Args:
            code: 종목코드.
            date: 기준일.
            rows: (period, indicator, value) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO investment_indicators "
                "(code, date, period, indicator, value) "
                "VALUES (?, ?, ?, ?, ?)",
                [(code, date, p, ind, val) for p, ind, val in rows],
            )

    def get_investment_indicators(
        self, code: str, indicator: str | None = None,
    ) -> list[dict]:
        """투자지표 시계열을 조회한다."""
        query = (
            "SELECT * FROM investment_indicators "
            "WHERE code = ?"
        )
        params: list = [code]
        if indicator:
            query += " AND indicator = ?"
            params.append(indicator)
        query += " ORDER BY date DESC, period"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── Consensus Estimates (c1050001) ────────────────────────────

    def save_consensus_estimates(
        self, code: str, date: str, rows: list[tuple],
    ) -> None:
        """컨센서스 추정실적을 저장한다.

        Args:
            code: 종목코드.
            date: 기준일.
            rows: (period, revenue, op_profit, net_income, eps, per, analyst_count) 튜플.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO consensus_estimates "
                "(code, date, period, revenue, operating_profit, "
                "net_income, eps, per, analyst_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (code, date, p, rev, op, ni, eps, per, ac)
                    for p, rev, op, ni, eps, per, ac in rows
                ],
            )

    def get_consensus_estimates(self, code: str) -> list[dict]:
        """가장 최근 컨센서스 추정실적을 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM consensus_estimates "
                "WHERE code = ? ORDER BY date DESC, period",
                (code,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Sector Comparison (c1060001) ──────────────────────────────

    def save_sector_comparison(self, code: str, date: str, **kwargs) -> None:
        """업종 비교 데이터를 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sector_comparison "
                "(code, date, sector, rank_in_sector, "
                "sector_per, sector_pbr, comparison_data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    code, date,
                    kwargs.get("sector"),
                    kwargs.get("rank_in_sector"),
                    kwargs.get("sector_per"),
                    kwargs.get("sector_pbr"),
                    kwargs.get("comparison_data"),
                ),
            )

    def get_sector_comparison(self, code: str) -> dict | None:
        """가장 최근 업종 비교 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sector_comparison "
                "WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    # ── Shareholder Data (c1070001) ───────────────────────────────

    _SHAREHOLDER_COLUMNS = (
        "largest_holder", "largest_pct", "foreign_pct",
        "institutional_pct", "float_pct", "float_shares", "changes",
    )

    def save_shareholder_data(self, code: str, date: str, **kwargs) -> None:
        """지분 현황 데이터를 저장한다."""
        cols = ", ".join(self._SHAREHOLDER_COLUMNS)
        placeholders = ", ".join("?" for _ in self._SHAREHOLDER_COLUMNS)
        values = tuple(kwargs.get(c) for c in self._SHAREHOLDER_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO shareholder_data "
                f"(code, date, {cols}) VALUES (?, ?, {placeholders})",
                (code, date, *values),
            )

    def get_shareholder_data(self, code: str) -> dict | None:
        """가장 최근 지분 현황 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM shareholder_data "
                "WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    # ── Analyst Reports (c1080001) ────────────────────────────────

    def save_analyst_reports(self, code: str, rows: list[tuple]) -> None:
        """증권사 리포트 목록을 저장한다.

        Args:
            code: 종목코드.
            rows: (report_date, analyst, provider, title, opinion, target_price) 튜플.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO analyst_reports "
                "(code, report_date, analyst, provider, "
                "title, opinion, target_price) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (code, rd, a, p, t, o, tp)
                    for rd, a, p, t, o, tp in rows
                ],
            )

    def get_analyst_reports(
        self, code: str, limit: int = 20,
    ) -> list[dict]:
        """증권사 리포트 목록을 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM analyst_reports "
                "WHERE code = ? ORDER BY report_date DESC LIMIT ?",
                (code, limit),
            ).fetchall()
        return [dict(r) for r in rows]
