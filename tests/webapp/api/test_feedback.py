"""Feedback API — summary/history/detail GET endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.api.feedback import router as feedback_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def feedback_store(tmp_path):
    return FeedbackStore(db_path=tmp_path / "feedback.db")


@pytest.fixture
def feedback_evaluator(feedback_store):
    return FeedbackEvaluator(store=feedback_store)


@pytest.fixture
def app(webapp_db, feedback_store, feedback_evaluator):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.state.feedback_store = feedback_store
    app.state.feedback_evaluator = feedback_evaluator
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(feedback_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/csrf-token")
    token = r.json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"x-csrf-token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


def _save_full(store, date: str, *,
               score: float = 40.0, signal: str = "moderately_bullish",
               indicator_scores: dict | None = None,
               kospi_change: float = 0.8,
               return_1d: float | None = 0.8, hit_1d: int | None = 1,
               return_3d: float | None = -0.3, hit_3d: int | None = 0,
               return_5d: float | None = 1.5, hit_5d: int | None = 1,
               post_analysis: str | None = None,
               news_summary: str | None = None,
               blind_spots: str | None = None) -> None:
    """헬퍼 — 완전한 feedback row 삽입 (평가 완료 상태).

    FeedbackStore.update_result 는 return_1d/hit_1d 를 함께 요구하므로
    여기서 한 번에 넣고, 3d/5d 만 update_returns 로 부분 업데이트한다.
    hit_5d=None 같은 부분 평가 상태는 raw SQL 로 NULL 을 다시 세팅한다.
    """
    import sqlite3

    store.save_signal(date, score, signal, indicator_scores or {"investor_flow": 60.0})
    store.update_result(
        date,
        kospi_close=2700.0, kospi_change_pct=kospi_change,
        kosdaq_close=850.0, kosdaq_change_pct=0.5,
        return_1d=return_1d if return_1d is not None else 0.0,
        hit_1d=hit_1d if hit_1d is not None else 0,
    )
    # 3d/5d 부분 업데이트
    kwargs = {}
    if return_3d is not None:
        kwargs["return_3d"] = return_3d
    if hit_3d is not None:
        kwargs["hit_3d"] = hit_3d
    if return_5d is not None:
        kwargs["return_5d"] = return_5d
    if hit_5d is not None:
        kwargs["hit_5d"] = hit_5d
    if kwargs:
        store.update_returns(date, **kwargs)

    # None 을 요청한 필드는 NULL 로 되돌림 (update_result 가 0.0 을 세팅하므로)
    null_fields = []
    if return_1d is None:
        null_fields.append("return_1d")
    if hit_1d is None:
        null_fields.append("hit_1d")
    if hit_5d is None:
        null_fields.append("hit_5d")
    if return_5d is None:
        null_fields.append("return_5d")
    if hit_3d is None:
        null_fields.append("hit_3d")
    if return_3d is None:
        null_fields.append("return_3d")
    if null_fields:
        set_clause = ", ".join(f"{f} = NULL" for f in null_fields)
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                f"UPDATE signal_feedback SET {set_clause} WHERE date = ?",
                (date,),
            )

    if post_analysis or news_summary or blind_spots:
        store.update_analysis(
            date,
            post_analysis=post_analysis or "",
            news_summary=news_summary or "",
            blind_spots=blind_spots or "",
        )


def test_summary_empty_db(client):
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30
    assert body["hit_rates"]["total_evaluated"] == 0
    assert body["hit_rates"]["count_1d"] == 0
    assert body["correlation"] is None
    assert body["indicator_accuracy"] == []
    assert body["recent_history"] == []


def test_summary_returns_rates_and_accuracy(client, feedback_store):
    _save_full(feedback_store, "20260420", score=70.0, hit_1d=1, hit_3d=1, hit_5d=1,
               indicator_scores={"investor_flow": 60.0, "vkospi": 55.0})
    _save_full(feedback_store, "20260421", score=-70.0, hit_1d=1, hit_3d=0, hit_5d=1,
               indicator_scores={"investor_flow": -60.0, "vkospi": 10.0})
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["hit_rates"]["total_evaluated"] == 2
    assert body["hit_rates"]["hit_rate_1d"] == 1.0
    assert body["hit_rates"]["count_1d"] == 2
    # indicator_accuracy: investor_flow 둘 다 극단값 → count=2, accuracy=1.0; vkospi 하나만
    keys = [i["key"] for i in body["indicator_accuracy"]]
    assert "investor_flow" in keys
    # 정렬: accuracy 내림차순
    accs = [i["accuracy"] for i in body["indicator_accuracy"]]
    assert accs == sorted(accs, reverse=True)


def test_summary_excludes_zero_count_indicators(client, feedback_store):
    """모든 지표가 threshold 미만이면 제외."""
    _save_full(feedback_store, "20260421", score=10.0,
               indicator_scores={"investor_flow": 5.0})  # 극단값 아님
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.json()["indicator_accuracy"] == []


def test_summary_recent_history_has_10_max(client, feedback_store):
    """recent_history 는 최근 10건으로 제한."""
    for i in range(15):
        _save_full(feedback_store, f"202604{i+1:02d}")
    r = client.get("/api/v1/feedback/summary?days=30")
    body = r.json()
    assert len(body["recent_history"]) <= 10


def test_summary_days_out_of_range(client):
    r = client.get("/api/v1/feedback/summary?days=0")
    assert r.status_code == 422
    r = client.get("/api/v1/feedback/summary?days=500")
    assert r.status_code == 422


def test_history_returns_paginated(client, feedback_store):
    for i in range(25):
        _save_full(feedback_store, f"202604{i+1:02d}")
    r = client.get("/api/v1/feedback/history?days=60&page=1&size=10")
    body = r.json()
    assert body["total"] == 25
    assert body["page"] == 1
    assert body["size"] == 10
    assert len(body["items"]) == 10


def test_history_returns_bool_hit_flags(client, feedback_store):
    """DB 의 INTEGER 0/1/NULL 이 bool/None 으로 변환된다."""
    _save_full(feedback_store, "20260421", hit_1d=1, hit_3d=0, hit_5d=None)
    r = client.get("/api/v1/feedback/history?days=30")
    item = r.json()["items"][0]
    assert item["hit_1d"] is True
    assert item["hit_3d"] is False
    assert item["hit_5d"] is None


def test_history_size_out_of_range(client):
    r = client.get("/api/v1/feedback/history?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/feedback/history?size=500")
    assert r.status_code == 422


def test_detail_returns_full_row(client, feedback_store):
    _save_full(feedback_store, "20260421",
               post_analysis="종합분석", news_summary="뉴스요약", blind_spots="사각지대")
    r = client.get("/api/v1/feedback/20260421")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260421"
    assert body["score"] == 40.0
    assert body["kospi_change_pct"] == 0.8
    assert body["return_1d"] == 0.8
    assert body["hit_1d"] is True
    assert body["post_analysis"] == "종합분석"
    assert body["news_summary"] == "뉴스요약"
    assert body["blind_spots"] == "사각지대"
    assert isinstance(body["indicator_scores"], dict)


def test_detail_404_missing(client):
    r = client.get("/api/v1/feedback/19000101")
    assert r.status_code == 404


def test_detail_rejects_invalid_date_format(client):
    r = client.get("/api/v1/feedback/not-a-date")
    assert r.status_code == 422


def test_summary_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/feedback/summary")
    assert r.status_code == 401


def test_detail_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/feedback/20260421")
    assert r.status_code == 401


# _decode_text_field branch tests — verify helper handles JSON-encoded values
# from FeedbackStore.update_analysis (which json.dumps() post_analysis/blind_spots)


def test_decode_text_field_json_encoded_string():
    """update_analysis 가 문자열을 json.dumps 하면 앞뒤에 따옴표 붙음."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    assert _decode_text_field('"hello"') == "hello"


def test_decode_text_field_json_encoded_list():
    """list 는 comma-join 된 문자열로 반환."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    assert _decode_text_field('["a","b","c"]') == "a, b, c"


def test_decode_text_field_json_encoded_empty_list():
    """빈 list 는 None 반환."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    assert _decode_text_field('[]') is None


def test_decode_text_field_json_encoded_dict_returned_as_raw():
    """dict 는 frontend 가 처리할 수 있도록 원본 JSON 문자열로."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    raw = '{"section":"analysis","body":"text"}'
    result = _decode_text_field(raw)
    # 원본 그대로 또는 재직렬화 — 둘 다 허용
    assert result is not None
    assert "section" in result


def test_decode_text_field_invalid_json_returns_raw():
    """깨진 JSON 은 원본 문자열 그대로."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    assert _decode_text_field("not json") == "not json"


def test_decode_text_field_none_and_empty():
    """None 과 빈 문자열 모두 None 반환."""
    from alphapulse.webapp.api.feedback import _decode_text_field
    assert _decode_text_field(None) is None
    assert _decode_text_field("") is None
