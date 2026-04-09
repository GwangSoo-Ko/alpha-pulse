"""SQLite 기반 데이터 캐시

수집된 시장 데이터를 로컬 SQLite DB에 캐싱하여
반복 API 호출을 최소화한다.
"""

import sqlite3
import time
from io import StringIO
from pathlib import Path

import pandas as pd


class DataCache:
    """SQLite 기반 DataFrame 캐시.

    Attributes:
        db_path: SQLite 데이터베이스 파일 경로.
    """

    def __init__(self, db_path: Path | str) -> None:
        """캐시 초기화 및 테이블 생성.

        Args:
            db_path: SQLite DB 파일 경로.
        """
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """캐시 테이블이 없으면 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    created_at REAL
                )
                """
            )

    def get(self, key: str, ttl_minutes: int = 0) -> pd.DataFrame | None:
        """캐시에서 데이터를 조회한다.

        Args:
            key: 캐시 키.
            ttl_minutes: TTL(분). 0이면 만료되지 않는다.

        Returns:
            캐시된 DataFrame 또는 None (미존재/만료 시).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, created_at FROM cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        data_json, created_at = row

        if ttl_minutes > 0:
            elapsed_minutes = (time.time() - created_at) / 60.0
            if elapsed_minutes > ttl_minutes:
                return None

        return pd.read_json(StringIO(data_json))

    def set(self, key: str, data: pd.DataFrame) -> None:
        """데이터를 캐시에 저장(upsert)한다.

        Args:
            key: 캐시 키.
            data: 저장할 DataFrame.
        """
        # 중복 인덱스 처리: orient='split' 사용
        df = data.copy()
        if df.index.duplicated().any():
            df = df.reset_index(drop=True)
        data_json = df.to_json()
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cache (key, data, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    data = excluded.data,
                    created_at = excluded.created_at
                """,
                (key, data_json, now),
            )

    def clear(self) -> None:
        """모든 캐시 항목을 삭제한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")

    def clear_expired(self, ttl_minutes: int) -> None:
        """만료된 캐시 항목을 삭제한다.

        Args:
            ttl_minutes: TTL(분). 이 시간보다 오래된 항목을 삭제한다.
        """
        cutoff = time.time() - (ttl_minutes * 60.0)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM cache WHERE created_at < ?",
                (cutoff,),
            )
