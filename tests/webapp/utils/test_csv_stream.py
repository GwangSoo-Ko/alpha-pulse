"""CSV 스트리밍 응답 공용 유틸리티 테스트 — 실제 ASGI 경로로 검증."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.utils.csv_stream import (
    csv_filename,
    stream_csv_response,
)


def _make_client(rows, columns, filename="t.csv", chunk_size=1000):
    app = FastAPI()

    @app.get("/export")
    def export():
        return stream_csv_response(
            iter(rows), columns=columns, filename=filename, chunk_size=chunk_size,
        )

    return TestClient(app)


def test_stream_csv_response_includes_bom():
    client = _make_client([{"a": 1}], [("A", "a")])
    r = client.get("/export")
    assert r.status_code == 200
    assert r.text.startswith("\ufeff")


def test_stream_csv_response_writes_header_and_rows():
    client = _make_client(
        [{"name": "알파", "score": 62.5}, {"name": "베타", "score": -15.0}],
        [("이름", "name"), ("점수", "score")],
    )
    r = client.get("/export")
    body = r.text.lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0] == "이름,점수"
    assert lines[1] == "알파,62.5"
    assert lines[2] == "베타,-15.0"


def test_stream_csv_response_chunks_large_data():
    rows = [{"n": i} for i in range(2500)]
    client = _make_client(rows, [("N", "n")], chunk_size=1000)
    r = client.get("/export")
    lines = r.text.lstrip("\ufeff").strip().split("\r\n")
    assert lines[0] == "N"
    assert len(lines) == 2501


def test_stream_csv_response_empty_rows_only_header():
    client = _make_client([], [("A", "a"), ("B", "b")])
    r = client.get("/export")
    body = r.text.lstrip("\ufeff")
    assert body.strip() == "A,B"


def test_stream_csv_response_content_type_and_disposition():
    client = _make_client([], [("A", "a")], filename="my_file.csv")
    r = client.get("/export")
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert "my_file.csv" in r.headers["content-disposition"]


def test_stream_csv_response_handles_missing_keys():
    client = _make_client([{"a": 1}], [("A", "a"), ("B", "b")])
    r = client.get("/export")
    body = r.text.lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[1] == "1,"


def test_csv_filename_format():
    name = csv_filename("backtest", "trades")
    import re
    assert re.match(r"^backtest_trades_\d{8}_\d{6}\.csv$", name)
