"""Job dataclass — 백그라운드 작업 상태."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

JobStatus = Literal["pending", "running", "done", "failed", "cancelled"]
JobKind = Literal["backtest", "screening", "data_update"]


@dataclass
class Job:
    id: str
    kind: JobKind
    status: JobStatus
    progress: float = 0.0
    progress_text: str = ""
    params: dict = field(default_factory=dict)
    result_ref: str | None = None
    error: str | None = None
    user_id: int = 0
    tenant_id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None

    def params_json(self) -> str:
        return json.dumps(self.params, ensure_ascii=False)
