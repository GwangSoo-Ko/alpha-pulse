"""AuditLog 조회 어댑터 (data/audit.db)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuditEvent:
    id: int
    timestamp: float
    event_type: str
    component: str
    data: dict
    mode: str


class AuditReader:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def query(
        self,
        from_ts: float | None = None,
        to_ts: float | None = None,
        actor_email: str | None = None,
        action_prefix: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        where = []
        params: list = []
        if from_ts is not None:
            where.append("timestamp >= ?")
            params.append(from_ts)
        if to_ts is not None:
            where.append("timestamp <= ?")
            params.append(to_ts)
        if action_prefix:
            where.append("event_type LIKE ?")
            params.append(f"{action_prefix}%")
        where_sql = " AND ".join(where) if where else "1=1"
        offset = (page - 1) * size
        if not self.db_path.exists():
            return {"items": [], "page": page, "size": size, "total": 0}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM audit_log WHERE {where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM audit_log WHERE {where_sql} "
                f"ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                [*params, size, offset],
            ).fetchall()
        events = []
        for r in rows:
            data = self._parse_json(r["data"] if "data" in r.keys() else None)
            if actor_email:
                if data.get("email") != actor_email:
                    continue
            events.append(AuditEvent(
                id=r["id"],
                timestamp=r["timestamp"],
                event_type=r["event_type"],
                component=r["component"] if "component" in r.keys() else "",
                data=data,
                mode=r["mode"] if "mode" in r.keys() else "",
            ))
        return {
            "items": events, "page": page, "size": size, "total": total,
        }

    @staticmethod
    def _parse_json(val) -> dict:
        if not val:
            return {}
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return val
