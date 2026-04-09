"""AI 에이전트용 Market Data 접근 인터페이스.

v1.5에서 ADK FunctionTool로 확장 예정.
현재는 직접 호출 인터페이스만 제공.
"""


def get_market_pulse_score(date: str = "today") -> dict:
    """오늘의 Market Pulse Score와 10개 지표 점수를 반환."""
    from alphapulse.market.engine.signal_engine import SignalEngine
    engine = SignalEngine()
    result = engine.run(date if date != "today" else None)
    return {
        "score": result["score"],
        "signal": result["signal"],
        "indicators": result["indicator_scores"],
    }


def get_recent_content_analysis(hours: int = 24) -> list[str]:
    """최근 N시간 내 콘텐츠 분석 요약 목록."""
    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    orch = BriefingOrchestrator()
    return orch.collect_recent_content(hours=hours)


def get_pulse_history(days: int = 7) -> list[dict]:
    """최근 N일간 Market Pulse Score 이력."""
    from alphapulse.core.config import Config
    from alphapulse.core.storage import PulseHistory
    cfg = Config()
    history = PulseHistory(cfg.HISTORY_DB)
    return history.get_recent(days=days)
