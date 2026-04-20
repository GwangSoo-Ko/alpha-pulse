"""통합 테스트 - 전체 파이프라인 E2E"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from alphapulse.cli import cli
from alphapulse.core.storage import DataCache, PulseHistory
from alphapulse.market.engine.signal_engine import SignalEngine

# --- Mock 데이터 ---

def _mock_investor_trading(*args, **kwargs):
    return pd.DataFrame({
        "기관합계": [50_000_000_000, 30_000_000_000],
        "기타법인": [5_000_000_000, -2_000_000_000],
        "개인": [-80_000_000_000, -40_000_000_000],
        "외국인합계": [25_000_000_000, 12_000_000_000],
    })


def _mock_market_ohlcv(*args, **kwargs):
    return pd.DataFrame({
        "시가": [70000, 130000, 400000],
        "고가": [71000, 132000, 410000],
        "저가": [69000, 128000, 395000],
        "종가": [70500, 131000, 405000],
        "거래량": [1000000, 500000, 200000],
        "등락률": [1.5, -0.8, 2.1],
    }, index=["005930", "000660", "373220"])


def _mock_exchange_rate(*args, **kwargs):
    return pd.DataFrame({"Close": [1340.0, 1335.0, 1330.0]})


def _mock_global_indices(*args, **kwargs):
    return {
        "SP500": pd.DataFrame({"Close": [5000, 5050]}),
        "NASDAQ": pd.DataFrame({"Close": [16000, 16200]}),
    }


def _mock_empty_df(*args, **kwargs):
    return pd.DataFrame()


def _mock_vkospi(*args, **kwargs):
    return pd.DataFrame({"Close": [18.5]})


def _mock_bond_yields(*args, **kwargs):
    return pd.DataFrame({"rate": [3.5]})


def _mock_us_treasury(*args, **kwargs):
    return pd.DataFrame({"rate": [4.3]})


def _mock_sector_perf(*args, **kwargs):
    return pd.DataFrame({
        "업종명": ["전기전자", "화학", "금융"],
        "등락률": [2.5, -0.5, 1.0],
    })


class TestSignalEngineIntegration:
    """시그널 엔진 E2E 테스트 (모든 외부 API Mock)"""

    @pytest.fixture
    def engine(self, tmp_path):
        cache = DataCache(str(tmp_path / "cache.db"))
        history = PulseHistory(str(tmp_path / "history.db"))
        return SignalEngine(cache=cache, history=history)

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_full_pipeline(self, mock_fdr, mock_stock, engine):
        """전체 파이프라인: 수집 → 분석 → 점수 → 결과"""
        # pykrx mocks
        mock_stock.get_market_trading_value_by_date.return_value = _mock_investor_trading()
        mock_stock.get_market_ohlcv_by_ticker.return_value = _mock_market_ohlcv()
        mock_stock.get_index_listing_date.return_value = pd.DataFrame()
        mock_stock.get_market_cap_by_ticker.return_value = pd.DataFrame()

        # FDR mocks
        mock_fdr.DataReader.side_effect = lambda ticker, *a, **kw: {
            "USD/KRW": _mock_exchange_rate(),
            "US500": pd.DataFrame({"Close": [5000, 5050]}),
            "IXIC": pd.DataFrame({"Close": [16000, 16200]}),
            "SSEC": pd.DataFrame({"Close": [3200, 3220]}),
            "N225": pd.DataFrame({"Close": [38000, 38200]}),
        }.get(ticker, pd.DataFrame({"Close": [3.5]}))

        # KRX scraper & FRED will fail gracefully (return empty or N/A)

        result = engine.run(date="20260313")

        assert "score" in result
        assert "signal" in result
        assert "indicator_scores" in result
        assert "details" in result
        assert isinstance(result["score"], float)
        assert -100 <= result["score"] <= 100

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_result_saved_to_history(self, mock_fdr, mock_stock, engine):
        """결과가 history DB에 저장되는지 확인"""
        mock_stock.get_market_trading_value_by_date.return_value = _mock_investor_trading()
        mock_stock.get_market_ohlcv_by_ticker.return_value = _mock_market_ohlcv()
        mock_stock.get_index_listing_date.return_value = pd.DataFrame()
        mock_fdr.DataReader.return_value = _mock_exchange_rate()

        # KRX scraper & FRED mocks
        engine.krx.get_spot_futures_trend = MagicMock(return_value={})
        engine.krx.get_sector_performance = MagicMock(return_value=pd.DataFrame())
        engine.krx.get_program_trading = MagicMock(return_value=pd.DataFrame())
        engine.krx.get_vkospi = MagicMock(return_value=pd.DataFrame())
        engine.krx.get_deposit = MagicMock(return_value=pd.DataFrame())
        engine.krx.get_credit_balance = MagicMock(return_value=pd.DataFrame())
        engine.fred.get_us_treasury_10y = MagicMock(return_value=pd.DataFrame({"DGS10": [4.25]}))
        engine.fred.get_kr_long_term_rate = MagicMock(return_value=pd.DataFrame({"IRLTLT01KRM156N": [3.5]}))

        engine.run(date="20260313")

        record = engine.history.get("20260313")
        assert record is not None
        assert "score" in record


class TestCLIIntegration:
    """CLI 명령어 통합 테스트"""

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "market" in result.output

    def test_market_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["market", "--help"])
        assert result.exit_code == 0
        assert "pulse" in result.output
        assert "investor" in result.output
        assert "macro" in result.output
        assert "program" in result.output
        assert "sector" in result.output
        assert "fund" in result.output
        assert "report" in result.output
        assert "history" in result.output

    def test_pulse_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["market", "pulse", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output
        assert "--period" in result.output

    def test_report_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["market", "report", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_investor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["market", "investor", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output

    def test_history_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["market", "history", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output

    def test_cache_clear(self, tmp_path):
        runner = CliRunner()
        with patch("alphapulse.core.config.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.CACHE_DB = str(tmp_path / "cache.db")
            mock_cfg_cls.return_value = mock_cfg
            with patch("alphapulse.core.storage.DataCache") as mock_dc_cls:
                mock_dc = MagicMock()
                mock_dc_cls.return_value = mock_dc
                result = runner.invoke(cli, ["cache", "clear"])
        assert result.exit_code == 0
        assert "캐시" in result.output

    def test_history_empty(self, tmp_path):
        runner = CliRunner()
        with patch("alphapulse.core.storage.history.PulseHistory.get_recent", return_value=[]):
            with patch("alphapulse.core.config.Config") as mock_cfg_cls:
                mock_cfg = MagicMock()
                mock_cfg.HISTORY_DB = str(tmp_path / "history.db")
                mock_cfg_cls.return_value = mock_cfg
                result = runner.invoke(cli, ["market", "history"])
                assert result.exit_code == 0


class TestTerminalReporter:
    """터미널 리포터 출력 테스트"""

    def test_print_pulse_report(self, capsys):
        from alphapulse.market.reporters.terminal import print_pulse_report

        result = {
            "date": "20260313",
            "period": "daily",
            "score": 42.5,
            "signal": "매수 우위 (Moderately Bullish)",
            "indicator_scores": {
                "investor_flow": 60,
                "spot_futures_align": 80,
                "program_trade": None,
                "sector_momentum": 30,
                "exchange_rate": 20,
                "vkospi": 30,
                "interest_rate_diff": -10,
                "global_market": 40,
                "fund_flow": None,
                "adr_volume": 25,
            },
            "details": {
                "investor_flow": {"details": "외국인 순매수: 370억원"},
                "spot_futures_align": {"details": "일치"},
                "sector_momentum": {"details": "평균 등락률: 1.0%"},
                "exchange_rate": {"details": "USD/KRW 1,330.0"},
                "vkospi": {"details": "V-KOSPI: 18.50"},
                "interest_rate_diff": {"details": "미국 4.30% / 한국 3.50%"},
                "global_market": {"details": "SP500: +1.0%"},
                "adr_volume": {"details": "ADR: 1.50"},
            },
        }
        print_pulse_report(result)
        # Should not raise

    def test_print_investor_detail(self, capsys):
        from alphapulse.market.reporters.terminal import print_investor_detail

        result = {
            "details": {
                "investor_flow": {
                    "foreign_net": 37_000_000_000,
                    "institutional_net": 80_000_000_000,
                    "details": "test",
                },
                "spot_futures_align": {
                    "aligned": True,
                    "details": "외국인 현물 매수 / 선물 매수 → 일치",
                },
            }
        }
        print_investor_detail(result)

    def test_print_sector_detail(self, capsys):
        from alphapulse.market.reporters.terminal import print_sector_detail

        result = {
            "details": {
                "sector_momentum": {"details": "평균 등락률: 1.0%"},
                "adr_volume": {"details": "ADR: 1.50"},
            }
        }
        print_sector_detail(result)

    def test_print_macro_detail(self, capsys):
        from alphapulse.market.reporters.terminal import print_macro_detail

        result = {
            "details": {
                "exchange_rate": {"details": "USD/KRW 1,330.0"},
                "vkospi": {"details": "V-KOSPI: 18.50"},
                "interest_rate_diff": {"details": "미국 4.30%"},
                "global_market": {"details": "SP500: +1.0%"},
            }
        }
        print_macro_detail(result)

    def test_print_history(self, capsys):
        from alphapulse.market.reporters.terminal import print_history

        records = [
            {"date": "20260313", "score": 42.5, "signal": "매수 우위"},
            {"date": "20260312", "score": -15.0, "signal": "중립"},
        ]
        print_history(records)

    def test_print_history_empty(self, capsys):
        from alphapulse.market.reporters.terminal import print_history
        print_history([])


class TestHTMLReport:
    """HTML 리포트 생성 테스트"""

    def test_generate_report(self, tmp_path):
        from alphapulse.market.reporters.html_report import generate_html_report

        result = {
            "date": "20260313",
            "period": "daily",
            "score": 42.5,
            "signal": "매수 우위 (Moderately Bullish)",
            "indicator_scores": {
                "investor_flow": 60,
                "spot_futures_align": 80,
                "program_trade": None,
                "sector_momentum": 30,
                "exchange_rate": 20,
                "vkospi": 30,
                "interest_rate_diff": -10,
                "global_market": 40,
                "fund_flow": None,
                "adr_volume": 25,
            },
            "details": {
                "investor_flow": {"details": "외국인 순매수: 370억원 | 기관 순매수: 800억원"},
                "spot_futures_align": {"details": "외국인 현물 매수 / 선물 매수 → 일치"},
                "sector_momentum": {"details": "평균 등락률: 1.0%"},
                "exchange_rate": {"details": "USD/KRW 1,330.0 (원화 강세)"},
                "vkospi": {"details": "V-KOSPI: 18.50 (정상)"},
                "interest_rate_diff": {"details": "미국 4.30% / 한국 3.50%"},
                "global_market": {"details": "SP500: +1.0% | NASDAQ: +1.25%"},
                "adr_volume": {"details": "ADR: 1.50"},
            },
        }

        output = str(tmp_path / "test_report.html")
        path = generate_html_report(result, output)
        assert Path(path).exists()

        content = Path(path).read_text(encoding="utf-8")
        assert "K-Market Pulse" in content
        assert "42.5" in content or "+42.5" in content
        assert "매수 우위" in content
