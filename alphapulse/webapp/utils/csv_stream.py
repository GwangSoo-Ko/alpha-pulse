"""CSV 스트리밍 응답 공용 유틸리티."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse


class _SyncStreamingResponse(StreamingResponse):
    """body_iterator 를 sync iterator 로 유지하는 StreamingResponse.

    Starlette 0.x 는 sync iterable 을 iterate_in_threadpool 으로 async 래핑하는데,
    테스트에서 동기 순회(for chunk in r.body_iterator)가 필요하므로 직접 할당.
    """

    def __init__(self, content: Iterator[str], **kwargs: Any) -> None:
        super().__init__(content=content, **kwargs)
        # Starlette 가 async 로 래핑한 것을 원래 sync iterator 로 되돌림
        self.body_iterator = content  # type: ignore[assignment]


def stream_csv_response(
    rows: Iterable[dict[str, Any]],
    *,
    columns: list[tuple[str, str]],
    filename: str,
    chunk_size: int = 1000,
) -> StreamingResponse:
    """dict iterable 을 CSV 로 스트리밍 (UTF-8 BOM 포함).

    Args:
        rows: dict iterable. 각 dict 는 columns 의 key 에 해당하는 값 보유.
        columns: [(header_label, dict_key), ...]. 순서대로 컬럼.
        filename: Content-Disposition 에 포함될 파일명.
        chunk_size: 몇 행마다 yield 할지 (메모리 제어).

    Returns:
        StreamingResponse with UTF-8 BOM + header + body.
    """

    def _iter_csv() -> Iterator[str]:
        yield "\ufeff"  # Excel 한글 호환 BOM
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

    return _SyncStreamingResponse(
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
