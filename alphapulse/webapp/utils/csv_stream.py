"""CSV 스트리밍 응답 공용 유틸리티."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse


def stream_csv_response(
    rows: Iterable[dict[str, Any]],
    *,
    columns: list[tuple[str, str]],
    filename: str,
    chunk_size: int = 1000,
) -> StreamingResponse:
    """dict iterable 을 CSV 로 스트리밍 (UTF-8 BOM 포함)."""

    def _iter_csv():
        yield "\ufeff"
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([label for label, _ in columns])
        yield buf.getvalue()
        buf = io.StringIO()
        writer = csv.writer(buf)
        count = 0
        for row in rows:
            writer.writerow([row.get(key, "") for _, key in columns])
            count += 1
            if count % chunk_size == 0:
                yield buf.getvalue()
                buf = io.StringIO()
                writer = csv.writer(buf)
        if buf.getvalue():
            yield buf.getvalue()

    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def csv_filename(domain: str, resource: str) -> str:
    """{domain}_{resource}_{YYYYMMDD_HHMMSS}.csv"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{domain}_{resource}_{ts}.csv"
