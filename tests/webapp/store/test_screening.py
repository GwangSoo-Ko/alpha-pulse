"""ScreeningRepository."""
import pytest

from alphapulse.webapp.store.screening import ScreeningRepository


@pytest.fixture
def repo(webapp_db):
    return ScreeningRepository(db_path=webapp_db)


class TestScreening:
    def test_save_and_get(self, repo):
        rid = repo.save(
            name="test", market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 0.5, "value": 0.5},
            top_n=10, market_context={"pulse_signal": "moderately_bullish"},
            results=[{"code": "005930", "name": "삼성전자", "score": 85.0}],
            user_id=1,
        )
        run = repo.get(rid)
        assert run is not None
        assert run.market == "KOSPI"
        assert run.strategy == "momentum"
        assert run.top_n == 10
        assert run.factor_weights["momentum"] == 0.5
        assert len(run.results) == 1
        assert run.results[0]["code"] == "005930"

    def test_list_for_user(self, repo):
        rid1 = repo.save(
            name="r1", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        rid2 = repo.save(
            name="r2", market="KOSDAQ", strategy="value",
            factor_weights={}, top_n=20, market_context={},
            results=[], user_id=1,
        )
        repo.save(
            name="other_user", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=2,
        )
        runs = repo.list_for_user(user_id=1, page=1, size=20)
        assert runs.total == 2
        assert {r.run_id for r in runs.items} == {rid1, rid2}

    def test_delete(self, repo):
        rid = repo.save(
            name="r", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        repo.delete(rid)
        assert repo.get(rid) is None

    def test_get_missing(self, repo):
        assert repo.get("missing") is None

    def test_pagination(self, repo):
        for i in range(25):
            repo.save(
                name=f"r{i}", market="KOSPI", strategy="momentum",
                factor_weights={}, top_n=10, market_context={},
                results=[], user_id=1,
            )
        p1 = repo.list_for_user(user_id=1, page=1, size=10)
        p3 = repo.list_for_user(user_id=1, page=3, size=10)
        assert p1.total == 25
        assert len(p1.items) == 10
        assert len(p3.items) == 5
