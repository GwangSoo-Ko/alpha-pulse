"""감사 추적 로거.

모든 매매 의사결정(시그널, AI 판단, 리스크 결정, 주문)을 SQLite에 기록한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class AuditLogger:
    """감사 추적 로거.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        """AuditLogger를 초기화한다.

        Args:
            db_path: 데이터베이스 파일 경로.
        """
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """audit_log 테이블이 없으면 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    data TEXT NOT NULL,
                    mode TEXT NOT NULL
                )
                """
            )

    def log(self, event_type: str, component: str,
            data: dict, mode: str) -> None:
        """이벤트를 기록한다.

        Args:
            event_type: 이벤트 유형 ("signal", "order", "risk_decision" 등).
            component: 발생 컴포넌트 ("momentum_strategy", "risk_manager" 등).
            data: 이벤트 상세 데이터 딕셔너리.
            mode: 실행 모드 ("backtest", "paper", "live").
        """
        data_json = json.dumps(data, ensure_ascii=False, default=str)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, component, data, mode) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), event_type, component, data_json, str(mode)),
            )

    def query(self, event_type: str | None = None,
              start: str | None = None,
              end: str | None = None) -> list[dict]:
        """이벤트를 조회한다.

        Args:
            event_type: 필터링할 이벤트 유형 (None이면 전체).
            start: 시작일 YYYYMMDD (None이면 제한 없음).
            end: 종료일 YYYYMMDD (None이면 제한 없음).

        Returns:
            이벤트 딕셔너리 리스트 (최신순).
        """
        conditions = []
        params: list = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)

        if start is not None:
            from datetime import datetime
            start_ts = datetime.strptime(start, "%Y%m%d").timestamp()
            conditions.append("timestamp >= ?")
            params.append(start_ts)

        if end is not None:
            from datetime import datetime, timedelta
            end_ts = (datetime.strptime(end, "%Y%m%d") + timedelta(days=1)).timestamp()
            conditions.append("timestamp < ?")
            params.append(end_ts)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC",
                params,
            )
            return [dict(row) for row in cursor.fetchall()]
