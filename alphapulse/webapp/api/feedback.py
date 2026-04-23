"""Feedback API — 시그널 적중률 / 지표별 정확도 / 이력 조회 (read-only)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class HitRates(BaseModel):
    total_evaluated: int
    hit_rate_1d: float | None
    hit_rate_3d: float | None
    hit_rate_5d: float | None
    count_1d: int
    count_3d: int
    count_5d: int


class IndicatorAccuracy(BaseModel):
    key: str
    accuracy: float
    count: int


class SignalHistoryItem(BaseModel):
    date: str
    score: float
    signal: str
    kospi_change_pct: float | None
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    hit_1d: bool | None
    hit_3d: bool | None
    hit_5d: bool | None


class FeedbackSummaryResponse(BaseModel):
    days: int
    hit_rates: HitRates
    correlation: float | None
    indicator_accuracy: list[IndicatorAccuracy]
    recent_history: list[SignalHistoryItem]


class FeedbackHistoryResponse(BaseModel):
    items: list[SignalHistoryItem]
    page: int
    size: int
    total: int


class FeedbackDetail(BaseModel):
    date: str
    score: float
    signal: str
    indicator_scores: dict[str, float | None]
    kospi_close: float | None
    kospi_change_pct: float | None
    kosdaq_close: float | None
    kosdaq_change_pct: float | None
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    hit_1d: bool | None
    hit_3d: bool | None
    hit_5d: bool | None
    post_analysis: str | None
    news_summary: str | None
    blind_spots: str | None
    evaluated_at: float | None
    created_at: float


class HitRateTrendPoint(BaseModel):
    date: str
    rolling_hit_rate_1d: float | None


class ScoreReturnPoint(BaseModel):
    date: str
    score: float
    return_1d: float
    signal: str


class IndicatorHeatmapCell(BaseModel):
    date: str
    indicator: str
    score: float


class SignalBreakdownRow(BaseModel):
    signal: str
    count: int
    hit_rate_1d: float | None
    hit_rate_3d: float | None
    hit_rate_5d: float | None


class AnalyticsResponse(BaseModel):
    days: int
    hit_rate_trend: list[HitRateTrendPoint]
    score_return_points: list[ScoreReturnPoint]
    indicator_heatmap: list[IndicatorHeatmapCell]
    signal_breakdown: list[SignalBreakdownRow]


def get_feedback_store(request: Request) -> FeedbackStore:
    return request.app.state.feedback_store


def get_feedback_evaluator(request: Request) -> FeedbackEvaluator:
    """매 요청마다 새 FeedbackEvaluator 인스턴스를 생성한다.

    Evaluator 내부 record 캐시가 인스턴스 생명주기 = 요청 생명주기 내에서만
    유효하도록 request-scoped 로 구성. 싱글턴 대신 store 만 공유.
    """
    store = request.app.state.feedback_store
    return FeedbackEvaluator(store=store)


def _int_to_bool(v: int | None) -> bool | None:
    if v is None:
        return None
    return bool(v)


def _parse_indicator_scores(raw) -> dict[str, float | None]:
    """DB 에서 온 indicator_scores 는 JSON 문자열 또는 이미 dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _decode_text_field(raw) -> str | None:
    """DB 의 post_analysis/blind_spots 는 JSON 인코딩되어 저장될 수 있음.

    - None → None
    - 빈 문자열 → None
    - 유효 JSON 문자열/리스트/딕셔너리 → 자연스러운 표현
    - 그 외 → 원본 문자열 그대로
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        return str(raw)
    if raw == "":
        return None
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if isinstance(decoded, str):
        return decoded
    if isinstance(decoded, list):
        return ", ".join(str(x) for x in decoded) if decoded else None
    if isinstance(decoded, dict):
        # dict 는 JSON 문자열 그대로 반환 (프론트엔드에서 처리)
        return raw
    return raw


def _row_to_history_item(row: dict) -> SignalHistoryItem:
    return SignalHistoryItem(
        date=row["date"],
        score=float(row["score"] or 0.0),
        signal=str(row["signal"] or ""),
        kospi_change_pct=row.get("kospi_change_pct"),
        return_1d=row.get("return_1d"),
        return_3d=row.get("return_3d"),
        return_5d=row.get("return_5d"),
        hit_1d=_int_to_bool(row.get("hit_1d")),
        hit_3d=_int_to_bool(row.get("hit_3d")),
        hit_5d=_int_to_bool(row.get("hit_5d")),
    )


def _row_to_detail(row: dict) -> FeedbackDetail:
    return FeedbackDetail(
        date=row["date"],
        score=float(row["score"] or 0.0),
        signal=str(row["signal"] or ""),
        indicator_scores=_parse_indicator_scores(row.get("indicator_scores")),
        kospi_close=row.get("kospi_close"),
        kospi_change_pct=row.get("kospi_change_pct"),
        kosdaq_close=row.get("kosdaq_close"),
        kosdaq_change_pct=row.get("kosdaq_change_pct"),
        return_1d=row.get("return_1d"),
        return_3d=row.get("return_3d"),
        return_5d=row.get("return_5d"),
        hit_1d=_int_to_bool(row.get("hit_1d")),
        hit_3d=_int_to_bool(row.get("hit_3d")),
        hit_5d=_int_to_bool(row.get("hit_5d")),
        post_analysis=_decode_text_field(row.get("post_analysis")),
        news_summary=row.get("news_summary") or None,
        blind_spots=_decode_text_field(row.get("blind_spots")),
        evaluated_at=row.get("evaluated_at"),
        created_at=row["created_at"],
    )


def _indicator_accuracy_list(raw: dict) -> list[IndicatorAccuracy]:
    """Evaluator dict → 정렬된 list. count=0 은 제외."""
    items = [
        IndicatorAccuracy(
            key=k,
            accuracy=v.get("accuracy", 0.0),
            count=v.get("total", 0),
        )
        for k, v in raw.items()
        if v.get("total", 0) > 0
    ]
    items.sort(key=lambda x: x.accuracy, reverse=True)
    return items


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_summary(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
    store: FeedbackStore = Depends(get_feedback_store),
):
    rates_raw = evaluator.get_hit_rates(days)
    correlation = evaluator.get_correlation(days)
    accuracy_raw = evaluator.get_indicator_accuracy(days)
    recent = store.get_recent(limit=10)

    # 빈 데이터: hit_rate_* 는 evaluator 가 0.0 반환하지만 spec 는 null 선호
    total = rates_raw.get("total_evaluated", 0)
    hit_rates = HitRates(
        total_evaluated=total,
        hit_rate_1d=rates_raw.get("hit_rate_1d") if total > 0 else None,
        hit_rate_3d=rates_raw.get("hit_rate_3d") if total > 0 else None,
        hit_rate_5d=rates_raw.get("hit_rate_5d") if total > 0 else None,
        count_1d=rates_raw.get("count_1d", 0),
        count_3d=rates_raw.get("count_3d", 0),
        count_5d=rates_raw.get("count_5d", 0),
    )

    return FeedbackSummaryResponse(
        days=days,
        hit_rates=hit_rates,
        correlation=correlation,
        indicator_accuracy=_indicator_accuracy_list(accuracy_raw),
        recent_history=[_row_to_history_item(r) for r in recent],
    )


@router.get("/history", response_model=FeedbackHistoryResponse)
async def get_history(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    rows = store.get_recent(limit=days)
    total = len(rows)
    start = (page - 1) * size
    sliced = rows[start:start + size]
    return FeedbackHistoryResponse(
        items=[_row_to_history_item(r) for r in sliced],
        page=page,
        size=size,
        total=total,
    )


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
):
    """4개 시각화 데이터셋 번들 (one-pass)."""
    bundle = evaluator.get_all_analytics(days=days)
    return AnalyticsResponse(
        days=days,
        hit_rate_trend=[HitRateTrendPoint(**p) for p in bundle["hit_rate_trend"]],
        score_return_points=[ScoreReturnPoint(**p) for p in bundle["score_return_points"]],
        indicator_heatmap=[IndicatorHeatmapCell(**c) for c in bundle["indicator_heatmap"]],
        signal_breakdown=[SignalBreakdownRow(**r) for r in bundle["signal_breakdown"]],
    )


@router.get("/{date}", response_model=FeedbackDetail)
async def get_detail(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    row = store.get(date)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Feedback not found for {date}",
        )
    return _row_to_detail(row)
