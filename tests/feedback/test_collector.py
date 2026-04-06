import pytest
from unittest.mock import patch, MagicMock
from alphapulse.feedback.collector import FeedbackCollector


@pytest.fixture
def collector(tmp_path):
    return FeedbackCollector(db_path=tmp_path / "feedback.db")


def test_calculate_hit_bullish():
    """매수 시그널 + 양수 수익률 = 적중"""
    from alphapulse.feedback.collector import calculate_hit
    assert calculate_hit(score=35.0, return_pct=1.2) == 1
    assert calculate_hit(score=35.0, return_pct=-0.5) == 0


def test_calculate_hit_bearish():
    """매도 시그널 + 음수 수익률 = 적중"""
    from alphapulse.feedback.collector import calculate_hit
    assert calculate_hit(score=-40.0, return_pct=-1.0) == 1
    assert calculate_hit(score=-40.0, return_pct=0.5) == 0


def test_calculate_hit_neutral():
    """중립 시그널 + 소폭 변동 = 적중"""
    from alphapulse.feedback.collector import calculate_hit
    assert calculate_hit(score=0.0, return_pct=0.3) == 1   # within ±0.5%
    assert calculate_hit(score=5.0, return_pct=1.5) == 0    # neutral but moved a lot


def test_collect_market_result(collector):
    """시장 결과 수집 (mock)"""
    with patch.object(collector, '_get_kospi_data') as mock_kospi, \
         patch.object(collector, '_get_kosdaq_data') as mock_kosdaq:
        mock_kospi.return_value = {"close": 2650.0, "change_pct": 1.2}
        mock_kosdaq.return_value = {"close": 870.0, "change_pct": 0.8}

        result = collector.collect_market_result("20260403")
        assert result["kospi_close"] == 2650.0
        assert result["kosdaq_close"] == 870.0


def test_calculate_returns(collector):
    """수익률 계산"""
    with patch.object(collector, '_get_kospi_close_series') as mock_series:
        # 시그널 발행일 종가 2600, D+1=2630, D+3=2650, D+5=2700
        mock_series.return_value = {
            "20260401": 2600.0,
            "20260402": 2630.0,
            "20260403": 2640.0,
            "20260404": 2650.0,
            "20260407": 2660.0,
            "20260408": 2700.0,
        }
        returns = collector.calculate_returns("20260401", base_close=2600.0)
        assert returns["return_1d"] is not None
        assert isinstance(returns["return_1d"], float)


def test_collect_and_evaluate(collector):
    """전체 수집+평가 파이프라인 (mock)"""
    # Save a pending signal first
    collector.store.save_signal("20260402", -20.0, "매도 우위", {"investor_flow": -80})

    with patch.object(collector, 'collect_market_result') as mock_result, \
         patch.object(collector, 'calculate_returns') as mock_returns:
        mock_result.return_value = {
            "kospi_close": 2600.0, "kospi_change_pct": -0.5,
            "kosdaq_close": 860.0, "kosdaq_change_pct": -0.3,
        }
        mock_returns.return_value = {
            "return_1d": -0.5, "return_3d": None, "return_5d": None,
        }
        collector.collect_and_evaluate()

    row = collector.store.get("20260402")
    assert row["kospi_close"] == 2600.0
    assert row["hit_1d"] == 1  # bearish signal + negative return = hit
