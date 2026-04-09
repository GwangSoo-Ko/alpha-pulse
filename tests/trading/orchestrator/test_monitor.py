"""SystemMonitor 테스트 — 시스템 헬스체크.

각 서브시스템의 상태를 점검하고 결과를 반환한다.
"""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.orchestrator.monitor import SystemMonitor


@pytest.fixture
def mock_components():
    """서브시스템 mock 딕셔너리."""
    return {
        "broker": MagicMock(),
        "data_provider": MagicMock(),
        "portfolio_store": MagicMock(),
        "risk_manager": MagicMock(),
    }


class TestHealthCheck:
    """헬스체크 테스트."""

    def test_all_healthy(self, mock_components):
        """모든 컴포넌트가 정상이면 healthy=True."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is True
        assert result["broker"]["status"] == "ok"
        assert result["data_provider"]["status"] == "ok"
        assert result["portfolio_store"]["status"] == "ok"

    def test_broker_failure(self, mock_components):
        """브로커 장애 시 healthy=False."""
        mock_components["broker"].get_balance.side_effect = Exception("연결 실패")
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["broker"]["status"] == "error"
        assert "연결 실패" in result["broker"]["message"]

    def test_data_provider_failure(self, mock_components):
        """데이터 소스 장애."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.side_effect = Exception("DB 오류")
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["data_provider"]["status"] == "error"

    def test_partial_failure(self, mock_components):
        """일부 장애는 전체 healthy=False."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.side_effect = Exception("디스크 오류")

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["broker"]["status"] == "ok"
        assert result["portfolio_store"]["status"] == "error"


class TestStatusSummary:
    """상태 요약 테스트."""

    def test_summary_includes_timestamp(self, mock_components):
        """상태에 타임스탬프가 포함된다."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()
        assert "timestamp" in result

    def test_summary_component_list(self, mock_components):
        """등록된 컴포넌트 목록을 반환한다."""
        monitor = SystemMonitor(components=mock_components)
        assert set(monitor.component_names()) == {
            "broker", "data_provider", "portfolio_store", "risk_manager",
        }
