"""Pulse Score 이력 관리

일자별 시황 점수와 시그널을 SQLite에 저장하여
시계열 추세 분석 및 리포트 생성에 활용한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class PulseHistory:
    """Pulse Score 이력 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 파일 경로.
    """

    def __init__(self, db_path: Path | str) -> None:
        """이력 DB 초기화 및 테이블 생성.

        Args:
            db_path: SQLite DB 파일 경로.
        """
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """이력 테이블이 없으면 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pulse_history (
                    date TEXT PRIMARY KEY,
                    score REAL,
                    signal TEXT,
                    details TEXT,
                    created_at REAL
                )
                """
            )

    def save(self, date: str, score: float, signal: str, details: dict) -> None:
        """Pulse Score 이력을 저장(upsert)한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).
            score: 종합 점수.
            signal: 시황 시그널 라벨.
            details: 세부 항목별 점수 딕셔너리.
        """
        details_json = json.dumps(details, ensure_ascii=False)
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pulse_history (date, score, signal, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    score = excluded.score,
                    signal = excluded.signal,
                    details = excluded.details,
                    created_at = excluded.created_at
                """,
                (date, score, signal, details_json, now),
            )

    def get(self, date: str) -> dict | None:
        """특정 날짜의 Pulse Score를 조회한다.

        Args:
            date: 조회할 날짜 (YYYYMMDD).

        Returns:
            이력 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT date, score, signal, details, created_at "
                "FROM pulse_history WHERE date = ?",
                (date,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def get_range(self, start: str, end: str) -> list[dict]:
        """날짜 범위의 Pulse Score 이력을 조회한다.

        Args:
            start: 시작 날짜 (YYYYMMDD, 포함).
            end: 종료 날짜 (YYYYMMDD, 포함).

        Returns:
            이력 딕셔너리 리스트 (날짜 오름차순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT date, score, signal, details, created_at "
                "FROM pulse_history "
                "WHERE date >= ? AND date <= ? "
                "ORDER BY date ASC",
                (start, end),
            )
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_recent(self, days: int = 30) -> list[dict]:
        """최근 N건의 Pulse Score 이력을 조회한다.

        Args:
            days: 조회할 최대 건수. 기본값 30.

        Returns:
            이력 딕셔너리 리스트 (날짜 내림차순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT date, score, signal, details, created_at "
                "FROM pulse_history "
                "ORDER BY date DESC "
                "LIMIT ?",
                (days,),
            )
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """sqlite3.Row를 딕셔너리로 변환한다.

        Args:
            row: SQLite Row 객체.

        Returns:
            변환된 딕셔너리. details 필드는 JSON 역직렬화된다.
        """
        return {
            "date": row["date"],
            "score": row["score"],
            "signal": row["signal"],
            "details": json.loads(row["details"]),
            "created_at": row["created_at"],
        }
