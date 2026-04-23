"""Briefing 결과 영속 저장소.

BriefingOrchestrator.run_async() 반환 dict 를 date 별로 JSON 으로 저장한다.
CLI daemon 과 웹 Job 둘 다 같은 테이블에 기록.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def _to_json_safe(value: Any) -> str:
    """payload dict 를 JSON 문자열로 직렬화 (numpy 타입 fallback 포함)."""
    return json.dumps(
        value,
        ensure_ascii=False,
        default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
    )


class BriefingStore:
    """Briefing 결과 영속 저장소 (`briefings` 테이블)."""

    def __init__(self, db_path: Path | str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS briefings (
                    date TEXT PRIMARY KEY,
                    payload TEXT,
                    created_at REAL
                )
                """
            )

    def save(self, date: str, payload: dict) -> None:
        """UPSERT. payload 안의 numpy/비직렬화 타입은 sanitize 된다."""
        # _to_json_safe 가 이미 모든 비 JSON 타입을 정규화하므로 단일 dump 로 충분
        final_text = _to_json_safe(payload)
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO briefings (date, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (date, final_text, now),
            )

    def get(self, date: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT date, payload, created_at FROM briefings WHERE date = ?",
                (date,),
            ).fetchone()
        if row is None:
            return None
        return {
            "date": row["date"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def get_recent(self, days: int = 30, offset: int = 0) -> list[dict]:
        """날짜 DESC 정렬, 최대 days 건. offset 으로 페이지네이션."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT date, payload, created_at FROM briefings "
                "ORDER BY date DESC LIMIT ? OFFSET ?",
                (days, offset),
            ).fetchall()
        return [
            {
                "date": r["date"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def list_summaries(self, limit: int, offset: int = 0) -> list[dict]:
        """payload 의 요약 필드만 json_extract 로 추출 (경량 목록용).

        Returns:
            [{date, created_at, score, signal, has_synthesis, has_commentary}]
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    date,
                    created_at,
                    json_extract(payload, '$.pulse_result.score') AS score,
                    json_extract(payload, '$.pulse_result.signal') AS signal,
                    (json_extract(payload, '$.synthesis') IS NOT NULL) AS has_synthesis,
                    (json_extract(payload, '$.commentary') IS NOT NULL) AS has_commentary
                FROM briefings
                ORDER BY date DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            {
                "date": r["date"],
                "created_at": r["created_at"],
                "score": float(r["score"]) if r["score"] is not None else 0.0,
                "signal": str(r["signal"]) if r["signal"] is not None else "",
                "has_synthesis": bool(r["has_synthesis"]),
                "has_commentary": bool(r["has_commentary"]),
            }
            for r in rows
        ]
