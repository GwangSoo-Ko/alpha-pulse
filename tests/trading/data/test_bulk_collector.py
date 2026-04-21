"""일괄 수집기 테스트 -- 네이버 금융 기반."""

from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.data.bulk_collector import BulkCollector

SAMPLE_SISE_HTML = """
<table class="type2">
<tr>
    <td><span>2025.04.04</span></td>
    <td><span>56,100</span></td>
    <td><span>하락</span></td>
    <td><span>56,200</span></td>
    <td><span>58,200</span></td>
    <td><span>55,700</span></td>
    <td><span>23,527,139</span></td>
</tr>
</table>
"""

SAMPLE_STOCK_LIST_HTML = """
<table>
<tr><td><a class="tltle" href="/item/main.naver?code=005930">삼성전자</a></td></tr>
</table>
"""


@pytest.fixture
def collector(tmp_path):
    return BulkCollector(db_path=tmp_path / "test.db", delay=0, years=1)


class TestBulkCollector:
    def test_collect_all_calls_collectors(self, collector):
        """전종목 수집이 수집기를 호출한다."""
        with patch.object(
            collector, "_find_latest_trading_date", return_value="20250404"
        ), patch.object(
            collector, "_collect_stock_list", return_value=["005930"]
        ), patch.object(
            collector.stock_collector, "collect_ohlcv"
        ), patch.object(
            collector.fundamental_collector, "collect"
        ), patch.object(
            collector, "_collect_flow_parallel"
        ):
            result = collector.collect_all(markets=["KOSPI"], resume=False)
            assert len(result) == 1
            assert result[0].market == "KOSPI"
            collector.stock_collector.collect_ohlcv.assert_called_once()
            collector.fundamental_collector.collect.assert_called_once()
            collector._collect_flow_parallel.assert_called_once()

    def test_update_when_never_collected(self, collector):
        """미수집 상태에서 update -> collect_all 폴백."""
        with patch.object(
            collector, "collect_all", return_value=[]
        ) as mock_collect:
            collector.update(markets=["KOSPI"])
            mock_collect.assert_called_once()

    def test_update_already_current(self, collector):
        """이미 최신이면 수집하지 않는다."""
        with patch.object(
            collector, "_find_latest_trading_date", return_value="20250404"
        ):
            collector.metadata.set_last_date("KOSPI", "ohlcv", "20250404")
            with patch.object(
                collector, "_collect_stock_list"
            ) as mock_collect:
                collector.update(markets=["KOSPI"])
                mock_collect.assert_not_called()

    def test_refresh_swallows_exceptions(self, collector):
        """refresh()는 예외를 전파하지 않는다."""
        with patch.object(collector, "update", side_effect=Exception("fail")):
            collector.refresh()  # should not raise

    def test_status(self, collector):
        """수집 현황을 반환한다."""
        collector.metadata.set_last_date("KOSPI", "ohlcv", "20250404")
        status = collector.status()
        assert "collection" in status
        assert len(status["collection"]) >= 1

    @patch("alphapulse.trading.data.bulk_collector.requests.get")
    def test_find_latest_trading_date(self, mock_get, collector):
        """네이버 금융에서 최근 거래일을 탐색한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = collector._find_latest_trading_date()
        assert result == "20250404"

    @patch("alphapulse.trading.data.bulk_collector.requests.get")
    def test_find_latest_trading_date_fallback(self, mock_get, collector):
        """네이버 금융 실패 시 어제 날짜를 반환한다."""
        mock_get.side_effect = Exception("network error")

        result = collector._find_latest_trading_date()
        # 어제 날짜 (YYYYMMDD 형식)
        assert len(result) == 8
        assert result.isdigit()

    def test_update_accepts_progress_callback_parameter(
        self, collector, monkeypatch,
    ):
        """update() 에 progress_callback 파라미터가 추가되어 backward-compat."""
        # _collect_stock_list 가 빈 리스트를 반환하여 phase 1 만 실행되고 종료
        monkeypatch.setattr(collector, "_collect_stock_list", lambda m: [])
        # 오늘 날짜를 미래로 세팅하여 증분 대상이 있다고 판단
        monkeypatch.setattr(
            collector, "_find_latest_trading_date", lambda: "20990101"
        )
        # 기존 last date 설정 → update 모드 진입
        collector.metadata.set_last_date("KOSPI", "ohlcv", "20250101")

        # None (backward-compat): 예외 없이 동작
        collector.update(markets=["KOSPI"], progress_callback=None)

        # 실제 callable: 예외 없이 동작
        events = []
        collector.update(
            markets=["KOSPI"],
            progress_callback=lambda p: events.append(p),
        )

    def test_update_emits_bulk_progress_events_for_phase_1(
        self, collector, monkeypatch,
    ):
        """update() 가 최소 phase 1 (종목 목록) BulkProgress 이벤트를 emit 한다."""
        from alphapulse.trading.data.bulk_collector import BulkProgress

        # 빈 코드 → phase 1 시작 이벤트만 발생 후 종료
        monkeypatch.setattr(collector, "_collect_stock_list", lambda m: [])
        monkeypatch.setattr(
            collector, "_find_latest_trading_date", lambda: "20990101"
        )
        collector.metadata.set_last_date("KOSPI", "ohlcv", "20250101")

        events: list[BulkProgress] = []
        collector.update(
            markets=["KOSPI"],
            progress_callback=lambda p: events.append(p),
        )

        # 최소 phase 1 시작 이벤트 1건 이상
        assert len(events) >= 1
        assert events[0].market == "KOSPI"
        assert events[0].market_idx == 1
        assert events[0].markets_total == 1
        assert events[0].phase_idx == 1
        assert events[0].phases_total == 5

    def test_collect_all_accepts_progress_callback_parameter(
        self, collector, monkeypatch,
    ):
        """collect_all() 도 progress_callback 을 받아 BulkProgress 를 emit 한다."""
        from alphapulse.trading.data.bulk_collector import BulkProgress

        # 빈 코드 → phase 1 이벤트 후 종료
        monkeypatch.setattr(collector, "_collect_stock_list", lambda m: [])
        monkeypatch.setattr(
            collector, "_find_latest_trading_date", lambda: "20990101"
        )

        # None (backward-compat): 기존 호출 시그니처도 유지됨
        collector.collect_all(markets=["KOSPI"], resume=False)

        events: list[BulkProgress] = []
        collector.collect_all(
            markets=["KOSPI"],
            resume=False,
            progress_callback=lambda p: events.append(p),
        )

        assert len(events) >= 1
        assert events[0].market == "KOSPI"
        assert events[0].market_idx == 1
        assert events[0].markets_total == 1
        assert events[0].phase_idx == 1
        assert events[0].phases_total == 5

    def test_update_passes_progress_callback_to_collect_all_on_fresh(
        self, collector, monkeypatch,
    ):
        """last 없음 → collect_all 위임 시 progress_callback 도 전달된다."""
        # last 가 None 이므로 update() → collect_all 폴백
        captured = {}

        def _fake_collect_all(
            markets=None, years=None, resume=True, progress_callback=None,
        ):
            captured["progress_callback"] = progress_callback
            captured["markets"] = markets
            return []

        monkeypatch.setattr(collector, "collect_all", _fake_collect_all)

        cb = lambda p: None  # noqa: E731
        collector.update(markets=["KOSPI"], progress_callback=cb)

        assert captured["progress_callback"] is cb
        assert captured["markets"] == ["KOSPI"]
