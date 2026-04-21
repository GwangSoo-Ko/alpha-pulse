"""Data Jobs — update/collect-* Job wrappers."""
from unittest.mock import MagicMock, patch

from alphapulse.webapp.services.data_jobs import (
    run_data_collect_financials,
    run_data_collect_short,
    run_data_collect_wisereport,
    run_data_update,
)


class TestDataJobs:
    @patch("alphapulse.webapp.services.data_jobs.BulkCollector")
    def test_update_calls_bulk_collector(self, mock_cls):
        inst = MagicMock()

        # Use a simple namespace object so attribute access works cleanly
        class _Result:
            market = "KOSPI"
            ohlcv_count = 10
            fundamentals_count = 0
            flow_count = 0
            wisereport_count = 0
            skipped = 0
            elapsed_seconds = 1.2

        inst.update.return_value = [_Result()]
        mock_cls.return_value = inst

        cb = MagicMock()
        result_json = run_data_update(
            markets=["KOSPI"], progress_callback=cb,
        )
        assert inst.update.called
        assert "KOSPI" in result_json

    @patch("alphapulse.webapp.services.data_jobs.FundamentalCollector")
    @patch("alphapulse.webapp.services.data_jobs.TradingStore")
    def test_collect_financials(self, mock_store_cls, mock_cls):
        inst = MagicMock()
        inst.collect.return_value = None  # actual return type is None
        mock_cls.return_value = inst

        store_inst = MagicMock()
        store_inst.get_all_stocks.return_value = [
            {"code": "005930", "market": "KOSPI", "name": "삼성전자"},
        ]
        mock_store_cls.return_value = store_inst

        cb = MagicMock()
        out = run_data_collect_financials(
            market="KOSPI", top=100, progress_callback=cb,
        )
        assert inst.collect.called
        assert "KOSPI" in out

    @patch("alphapulse.webapp.services.data_jobs.WisereportCollector")
    def test_collect_wisereport(self, mock_cls):
        inst = MagicMock()
        # actual return type is dict[str, dict]
        inst.collect_static_batch.return_value = {
            "005930": {"name": "삼성전자"},
            "000660": {"name": "SK하이닉스"},
        }
        mock_cls.return_value = inst
        cb = MagicMock()
        run_data_collect_wisereport(
            market="KOSPI", top=100, progress_callback=cb,
        )
        assert inst.collect_static_batch.called

    @patch("alphapulse.webapp.services.data_jobs.ShortCollector")
    @patch("alphapulse.webapp.services.data_jobs.TradingStore")
    def test_collect_short(self, mock_store_cls, mock_cls):
        inst = MagicMock()
        # ShortCollector.collect() returns None (just logs)
        inst.collect.return_value = None
        mock_cls.return_value = inst

        # stub TradingStore.get_all_stocks
        store_inst = MagicMock()
        store_inst.get_all_stocks.return_value = [
            {"code": "005930", "market": "KOSPI", "name": "삼성전자"},
        ]
        mock_store_cls.return_value = store_inst

        cb = MagicMock()
        out = run_data_collect_short(
            market="KOSPI", top=5, progress_callback=cb,
        )
        assert inst.collect.called
        assert "KOSPI" in out

    @patch("alphapulse.webapp.services.data_jobs.BulkCollector")
    def test_update_progress_callback_called(self, mock_cls):
        inst = MagicMock()
        inst.update.return_value = []
        mock_cls.return_value = inst

        calls = []
        run_data_update(
            markets=["KOSPI"],
            progress_callback=lambda cur, total, text="": calls.append((cur, total)),
        )
        assert len(calls) >= 2

    @patch("alphapulse.webapp.services.data_jobs.WisereportCollector")
    @patch("alphapulse.webapp.services.data_jobs.TradingStore")
    def test_collect_wisereport_filters_by_market(self, mock_store_cls, mock_wc_cls):
        inst = MagicMock()
        inst.collect_static_batch.return_value = {}
        mock_wc_cls.return_value = inst

        store_inst = MagicMock()
        store_inst.get_all_stocks.return_value = [
            {"code": "005930", "market": "KOSPI", "name": "삼성전자"},
            {"code": "035720", "market": "KOSDAQ", "name": "카카오"},
        ]
        mock_store_cls.return_value = store_inst

        cb = MagicMock()
        run_data_collect_wisereport(
            market="KOSPI", top=10, progress_callback=cb,
        )

        called_codes = inst.collect_static_batch.call_args[0][0]
        assert "005930" in called_codes
        assert "035720" not in called_codes

    @patch("alphapulse.webapp.services.data_jobs.BulkCollector")
    def test_run_data_update_bridges_bulk_progress_to_job_callback(
        self, mock_cls,
    ):
        """BulkProgress 이벤트가 Job progress_callback 으로 올바르게 브릿지된다."""
        from alphapulse.trading.data.bulk_collector import BulkProgress

        progress_calls: list[tuple[int, int, str]] = []

        def on_progress(current: int, total: int, text: str) -> None:
            progress_calls.append((current, total, text))

        mock_collector = MagicMock()

        def fake_update(*, markets, progress_callback):
            # 에뮬레이트: KOSPI 2/5 phase OHLCV 절반 진행
            progress_callback(BulkProgress(
                market="KOSPI", market_idx=1, markets_total=1,
                phase_idx=2, phases_total=5, phase_label="OHLCV",
                current=500, total=1000, detail="005930",
            ))
            return []

        mock_collector.update = fake_update
        mock_cls.return_value = mock_collector

        run_data_update(markets=["KOSPI"], progress_callback=on_progress)

        # (0,1,"시작"), bridge call, (1,1,"완료")
        assert progress_calls[0] == (0, 1, "증분 업데이트 시작")
        assert progress_calls[-1] == (1, 1, "완료")

        # Bridge middle call:
        # total_steps = 1 * 5 = 5
        # steps_done = (1-1)*5 + (2-1) = 1
        # phase_frac = 500/1000 = 0.5
        # overall_num = (1 + 0.5) * 1000 = 1500
        # overall_den = 5 * 1000 = 5000
        bridge = progress_calls[1]
        assert bridge[0] == 1500
        assert bridge[1] == 5000
        assert "[KOSPI]" in bridge[2]
        assert "[2/5]" in bridge[2]
        assert "OHLCV" in bridge[2]
        assert "500/1000" in bridge[2]
        assert "005930" in bridge[2]

    @patch("alphapulse.webapp.services.data_jobs.FundamentalCollector")
    @patch("alphapulse.webapp.services.data_jobs.TradingStore")
    def test_collect_financials_passes_progress_callback(
        self, mock_store_cls, mock_cls,
    ):
        """FundamentalCollector.collect 가 per-code progress_callback 을 받는다."""
        inst = MagicMock()

        def fake_collect(*, date, market, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback("005930")
                progress_callback("000660")

        inst.collect.side_effect = fake_collect
        mock_cls.return_value = inst

        store_inst = MagicMock()
        store_inst.get_all_stocks.return_value = [
            {"code": "005930", "market": "KOSPI", "name": "삼성전자"},
            {"code": "000660", "market": "KOSPI", "name": "SK하이닉스"},
        ]
        mock_store_cls.return_value = store_inst

        calls: list[tuple[int, int, str]] = []
        run_data_collect_financials(
            market="KOSPI", top=100,
            progress_callback=lambda cur, total, text="": calls.append(
                (cur, total, text)
            ),
        )

        # start, per-code (005930), per-code (000660), 완료
        assert any("005930" in c[2] for c in calls)
        assert any("000660" in c[2] for c in calls)
        # denominator 는 store 에서 해석된 실제 종목 수 (2)
        assert calls[-1] == (2, 2, "완료")
        # 시작 호출: (0, 2, ...)
        assert calls[0][0] == 0 and calls[0][1] == 2

    @patch("alphapulse.webapp.services.data_jobs.WisereportCollector")
    @patch("alphapulse.webapp.services.data_jobs.TradingStore")
    def test_collect_wisereport_passes_progress_callback(
        self, mock_store_cls, mock_wc_cls,
    ):
        """WisereportCollector.collect_static_batch 가 per-code progress_callback 을 받는다."""
        inst = MagicMock()

        def fake_batch(codes, today, progress_callback=None, **kwargs):
            if progress_callback:
                for code in codes:
                    progress_callback(code)
            return {}

        inst.collect_static_batch.side_effect = fake_batch
        mock_wc_cls.return_value = inst

        store_inst = MagicMock()
        store_inst.get_all_stocks.return_value = [
            {"code": "005930", "market": "KOSPI", "name": "삼성전자"},
            {"code": "000660", "market": "KOSPI", "name": "SK하이닉스"},
        ]
        mock_store_cls.return_value = store_inst

        calls: list[tuple[int, int, str]] = []
        run_data_collect_wisereport(
            market="KOSPI", top=10,
            progress_callback=lambda cur, total, text="": calls.append(
                (cur, total, text)
            ),
        )

        assert any("005930" in c[2] for c in calls)
        assert any("000660" in c[2] for c in calls)
        assert calls[-1][2] == "완료"
