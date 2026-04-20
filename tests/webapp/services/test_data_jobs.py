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
    def test_collect_financials(self, mock_cls):
        inst = MagicMock()
        inst.collect.return_value = None  # actual return type is None
        mock_cls.return_value = inst
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
