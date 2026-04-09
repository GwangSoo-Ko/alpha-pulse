"""팩터 계산 테스트."""

from alphapulse.trading.screening.factors import FactorCalculator


# ── 모멘텀 팩터 ──────────────────────────────────────────────────

class TestMomentum:
    """편의 메서드 momentum() 테스트."""

    def test_positive_return(self, trading_store):
        """상승 종목은 양수 모멘텀."""
        calc = FactorCalculator(trading_store)
        result = calc.momentum("005930", lookback=20)
        assert result > 0  # 70000 → 73800 상승

    def test_negative_return(self, trading_store):
        """하락 종목은 음수 모멘텀."""
        calc = FactorCalculator(trading_store)
        result = calc.momentum("000660", lookback=20)
        assert result < 0  # 190000 → 184300 하락


class TestMomentum3m:
    """momentum_3m 개별 팩터 테스트."""

    def test_positive_return(self, trading_store):
        """상승 종목은 양수."""
        calc = FactorCalculator(trading_store)
        # 데이터가 20일뿐이므로 60일 lookback에서 가용 데이터로 계산
        result = calc.momentum_3m("005930")
        assert result is not None
        assert result > 0

    def test_missing_data(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        assert calc.momentum_3m("999999") is None


# ── 밸류 팩터 ────────────────────────────────────────────────────

class TestValue:
    """편의 메서드 value() 테스트."""

    def test_lower_per_higher_score(self, trading_store):
        """PER이 낮을수록 밸류 점수가 높다."""
        calc = FactorCalculator(trading_store)
        samsung = calc.value("005930")  # PER 12.5
        hynix = calc.value("000660")    # PER 8.0
        assert hynix > samsung  # PER 낮은 SK하이닉스가 더 높은 밸류 점수


class TestValuePBR:
    """value_pbr 개별 팩터 테스트."""

    def test_lower_pbr_higher_score(self, trading_store):
        """PBR이 낮을수록 B/P가 높다."""
        calc = FactorCalculator(trading_store)
        samsung = calc.value_pbr("005930")  # PBR 1.3
        hynix = calc.value_pbr("000660")    # PBR 1.0
        assert hynix > samsung

    def test_missing_data(self, trading_store):
        """PBR 데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        assert calc.value_pbr("999999") is None


# ── 퀄리티 팩터 ──────────────────────────────────────────────────

class TestQuality:
    """편의 메서드 quality() 테스트."""

    def test_higher_roe_higher_score(self, trading_store):
        """ROE가 높을수록 퀄리티 점수가 높다."""
        calc = FactorCalculator(trading_store)
        samsung = calc.quality("005930")  # ROE 15.2
        hynix = calc.quality("000660")    # ROE 12.0
        assert samsung > hynix


# ── 수급 팩터 ────────────────────────────────────────────────────

class TestFlow:
    """편의 메서드 flow() 테스트."""

    def test_net_buy_positive(self, trading_store):
        """외국인 순매수 종목은 양수 수급 점수."""
        calc = FactorCalculator(trading_store)
        samsung = calc.flow("005930", days=20)
        assert samsung > 0  # 외국인 순매수 우세

    def test_net_sell_negative(self, trading_store):
        """외국인 순매도 종목은 음수 수급 점수."""
        calc = FactorCalculator(trading_store)
        hynix = calc.flow("000660", days=20)
        assert hynix < 0  # 외국인 순매도


class TestFlowInstitutional:
    """flow_institutional 개별 팩터 테스트."""

    def test_returns_value(self, trading_store):
        """기관 순매수 누적을 반환한다."""
        calc = FactorCalculator(trading_store)
        result = calc.flow_institutional("005930", days=20)
        assert result is not None
        # conftest: 기관 20e9 * 20일 = 400e9
        assert result > 0

    def test_missing_data(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        assert calc.flow_institutional("999999") is None


# ── 변동성 팩터 ──────────────────────────────────────────────────

class TestVolatility:
    """편의 메서드 volatility() 테스트."""

    def test_returns_positive(self, trading_store):
        """변동성은 항상 양수."""
        calc = FactorCalculator(trading_store)
        vol = calc.volatility("005930", days=20)
        assert vol > 0

    def test_missing_data_returns_none(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        vol = calc.volatility("999999", days=20)
        assert vol is None


class TestBeta:
    """beta 개별 팩터 테스트."""

    def test_returns_value(self, trading_store):
        """시장 베타를 반환한다."""
        calc = FactorCalculator(trading_store)
        result = calc.beta("005930")
        # 데이터 부족 시 None 가능하지만, 2종목 20일이면 계산 가능
        assert result is not None
        assert isinstance(result, float)

    def test_missing_data(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        assert calc.beta("999999") is None


# ── 역발상 팩터 ──────────────────────────────────────────────────

class TestShortDecrease:
    """short_decrease 개별 팩터 테스트."""

    def test_decreasing_short_positive(self, trading_store):
        """공매도 잔고 감소 시 양수."""
        calc = FactorCalculator(trading_store)
        # conftest: 삼성은 공매도 감소 추세
        result = calc.short_decrease("005930")
        assert result is not None
        assert result > 0

    def test_increasing_short_negative(self, trading_store):
        """공매도 잔고 증가 시 음수."""
        calc = FactorCalculator(trading_store)
        # conftest: SK하이닉스는 공매도 증가 추세
        result = calc.short_decrease("000660")
        assert result is not None
        assert result < 0

    def test_missing_data(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        assert calc.short_decrease("999999") is None
