"""Signal Feedback 저장소

일자별 시황 시그널과 사후 평가 결과를 SQLite에 저장하여
피드백 루프 분석 및 정확도 추적에 활용한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class FeedbackStore:
    """Signal Feedback 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 파일 경로.
    """

    def __init__(self, db_path: Path | str) -> None:
        """피드백 DB 초기화 및 테이블 생성.

        Args:
            db_path: SQLite DB 파일 경로.
        """
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """signal_feedback 테이블이 없으면 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_feedback (
                    date TEXT PRIMARY KEY,
                    score REAL,
                    signal TEXT,
                    indicator_scores TEXT,
                    kospi_close REAL,
                    kospi_change_pct REAL,
                    kosdaq_close REAL,
                    kosdaq_change_pct REAL,
                    return_1d REAL,
                    return_3d REAL,
                    return_5d REAL,
                    hit_1d INTEGER,
                    hit_3d INTEGER,
                    hit_5d INTEGER,
                    post_analysis TEXT,
                    news_summary TEXT,
                    blind_spots TEXT,
                    evaluated_at REAL,
                    created_at REAL
                )
                """
            )

    def save_signal(
        self,
        date: str,
        score: float,
        signal: str,
        indicator_scores: dict,
    ) -> None:
        """당일 시그널 결과를 저장(upsert)한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).
            score: 종합 점수.
            signal: 시황 시그널 라벨.
            indicator_scores: 지표별 점수 딕셔너리.
        """
        indicator_scores_json = json.dumps(
            indicator_scores,
            ensure_ascii=False,
            default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
        )
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO signal_feedback (date, score, signal, indicator_scores, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    score = excluded.score,
                    signal = excluded.signal,
                    indicator_scores = excluded.indicator_scores,
                    created_at = excluded.created_at
                """,
                (date, score, signal, indicator_scores_json, now),
            )

    def get(self, date: str) -> dict | None:
        """특정 날짜의 피드백 레코드를 조회한다.

        Args:
            date: 조회할 날짜 (YYYYMMDD).

        Returns:
            피드백 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM signal_feedback WHERE date = ?",
                (date,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    def update_result(
        self,
        date: str,
        kospi_close: float,
        kospi_change_pct: float,
        kosdaq_close: float,
        kosdaq_change_pct: float,
        return_1d: float,
        hit_1d: int,
    ) -> None:
        """시장 결과 데이터를 업데이트한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).
            kospi_close: 코스피 종가.
            kospi_change_pct: 코스피 등락률.
            kosdaq_close: 코스닥 종가.
            kosdaq_change_pct: 코스닥 등락률.
            return_1d: 1일 수익률.
            hit_1d: 1일 적중 여부 (1 or 0).
        """
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE signal_feedback SET
                    kospi_close = ?,
                    kospi_change_pct = ?,
                    kosdaq_close = ?,
                    kosdaq_change_pct = ?,
                    return_1d = ?,
                    hit_1d = ?,
                    evaluated_at = ?
                WHERE date = ?
                """,
                (
                    kospi_close,
                    kospi_change_pct,
                    kosdaq_close,
                    kosdaq_change_pct,
                    return_1d,
                    hit_1d,
                    now,
                    date,
                ),
            )

    def update_analysis(
        self,
        date: str,
        post_analysis: dict,
        news_summary: str,
        blind_spots: list,
    ) -> None:
        """사후 분석 결과를 업데이트한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).
            post_analysis: 사후 분석 딕셔너리.
            news_summary: 뉴스 요약 문자열.
            blind_spots: 발견된 블라인드 스팟 리스트.
        """
        post_analysis_json = json.dumps(
            post_analysis,
            ensure_ascii=False,
            default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
        )
        blind_spots_json = json.dumps(
            blind_spots,
            ensure_ascii=False,
            default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE signal_feedback SET
                    post_analysis = ?,
                    news_summary = ?,
                    blind_spots = ?
                WHERE date = ?
                """,
                (post_analysis_json, news_summary, blind_spots_json, date),
            )

    def update_returns(
        self,
        date: str,
        return_3d: float | None = None,
        hit_3d: int | None = None,
        return_5d: float | None = None,
        hit_5d: int | None = None,
    ) -> None:
        """3일/5일 수익률을 부분 업데이트한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).
            return_3d: 3일 수익률.
            hit_3d: 3일 적중 여부.
            return_5d: 5일 수익률.
            hit_5d: 5일 적중 여부.
        """
        updates = []
        params = []
        if return_3d is not None:
            updates.append("return_3d = ?")
            params.append(return_3d)
        if hit_3d is not None:
            updates.append("hit_3d = ?")
            params.append(hit_3d)
        if return_5d is not None:
            updates.append("return_5d = ?")
            params.append(return_5d)
        if hit_5d is not None:
            updates.append("hit_5d = ?")
            params.append(hit_5d)

        if not updates:
            return

        params.append(date)
        sql = f"UPDATE signal_feedback SET {', '.join(updates)} WHERE date = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, params)

    def get_recent(self, days: int = 30) -> list[dict]:
        """최근 N건의 피드백 레코드를 조회한다.

        Args:
            days: 조회할 최대 건수. 기본값 30.

        Returns:
            피드백 딕셔너리 리스트 (날짜 내림차순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM signal_feedback "
                "ORDER BY date DESC "
                "LIMIT ?",
                (days,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_pending_evaluation(self) -> list[dict]:
        """평가되지 않은 (return_1d가 NULL인) 레코드를 조회한다.

        Returns:
            미평가 피드백 딕셔너리 리스트 (날짜 오름차순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM signal_feedback "
                "WHERE return_1d IS NULL "
                "ORDER BY date ASC"
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_yesterday(self) -> dict | None:
        """가장 최근 기준 전일(두 번째로 최근) 레코드를 조회한다.

        Returns:
            전일 피드백 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM signal_feedback "
                "ORDER BY date DESC "
                "LIMIT 1 OFFSET 1"
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)
