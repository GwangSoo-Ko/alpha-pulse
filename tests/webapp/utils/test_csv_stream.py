"""CSV 스트리밍 응답 공용 유틸리티 테스트."""

from alphapulse.webapp.utils.csv_stream import (
    csv_filename,
    stream_csv_response,
)


def _consume(response) -> str:
    """StreamingResponse body iterator → 전체 문자열."""
    chunks = []
    for chunk in response.body_iterator:
        chunks.append(chunk)
    return "".join(chunks)


def test_stream_csv_response_includes_bom():
    rows = [{"a": 1}]
    cols = [("A", "a")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r)
    assert body.startswith("\ufeff")


def test_stream_csv_response_writes_header_and_rows():
    rows = [{"name": "알파", "score": 62.5}, {"name": "베타", "score": -15.0}]
    cols = [("이름", "name"), ("점수", "score")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r)
    body = body.lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0] == "이름,점수"
    assert lines[1] == "알파,62.5"
    assert lines[2] == "베타,-15.0"


def test_stream_csv_response_chunks_large_data():
    rows = ({"n": i} for i in range(2500))
    cols = [("N", "n")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv", chunk_size=1000)
    body = _consume(r)
    lines = body.lstrip("\ufeff").strip().split("\r\n")
    assert lines[0] == "N"
    assert len(lines) == 2501


def test_stream_csv_response_empty_rows_only_header():
    rows = iter([])
    cols = [("A", "a"), ("B", "b")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r).lstrip("\ufeff")
    assert body.strip() == "A,B"


def test_stream_csv_response_content_disposition_header():
    r = stream_csv_response(iter([]), columns=[("A", "a")], filename="my_file.csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "my_file.csv" in r.headers["content-disposition"]


def test_stream_csv_response_handles_missing_keys():
    rows = [{"a": 1}]
    cols = [("A", "a"), ("B", "b")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r).lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[1] == "1,"  # b 는 빈 문자열


def test_csv_filename_format():
    name = csv_filename("backtest", "trades")
    import re
    assert re.match(r"^backtest_trades_\d{8}_\d{6}\.csv$", name)
