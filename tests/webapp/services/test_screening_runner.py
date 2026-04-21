"""ScreeningRunner — CLI screen 로직 추출."""
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.webapp.services.screening_runner import run_screening_sync
from alphapulse.webapp.store.screening import ScreeningRepository


@pytest.fixture
def repo(webapp_db):
    return ScreeningRepository(db_path=webapp_db)


class TestScreeningRunner:
    @patch("alphapulse.webapp.services.screening_runner.TradingStore")
    @patch("alphapulse.webapp.services.screening_runner.FactorCalculator")
    @patch("alphapulse.webapp.services.screening_runner.MultiFactorRanker")
    @patch("alphapulse.webapp.services.screening_runner._load_universe")
    def test_runs_end_to_end(
        self, mock_load, mock_ranker_cls, mock_calc_cls, mock_store_cls,
        repo,
    ):
        from alphapulse.trading.core.models import Signal, Stock
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        mock_load.return_value = [stock]
        mock_calc = MagicMock()
        mock_calc.momentum.return_value = 50
        mock_calc.value.return_value = 30
        mock_calc.quality.return_value = 40
        mock_calc.growth.return_value = 50
        mock_calc.flow.return_value = 20
        mock_calc.volatility.return_value = 10
        mock_calc_cls.return_value = mock_calc
        mock_ranker = MagicMock()
        mock_ranker.rank.return_value = [
            Signal(
                stock=stock, score=80.0,
                factors={"momentum": 50}, strategy_id="momentum",
            ),
        ]
        mock_ranker_cls.return_value = mock_ranker

        progress = []
        def cb(cur, total, text=""):
            progress.append((cur, total, text))

        run_id = run_screening_sync(
            market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 0.5, "value": 0.5},
            top_n=10, name="test",
            screening_repo=repo, user_id=1,
            progress_callback=cb,
        )

        run = repo.get(run_id)
        assert run is not None
        assert run.market == "KOSPI"
        assert run.strategy == "momentum"
        assert len(run.results) == 1
        assert run.results[0]["code"] == "005930"
        assert run.results[0]["score"] == 80.0
        assert len(progress) >= 2

    def test_unknown_market_raises(self, repo):
        with pytest.raises(ValueError, match="market"):
            run_screening_sync(
                market="INVALID", strategy="momentum",
                factor_weights={}, top_n=10, name="",
                screening_repo=repo, user_id=1,
                progress_callback=lambda *a, **kw: None,
            )
