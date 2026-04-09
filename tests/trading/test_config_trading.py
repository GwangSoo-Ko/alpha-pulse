"""Trading Config 확장 테스트.

KIS API 및 Trading 관련 설정이 Config에 추가되었는지 검증한다.
"""

import os
from unittest.mock import patch

import pytest

from alphapulse.core.config import Config


class TestKISConfig:
    """KIS API 설정 테스트."""

    def test_default_kis_is_paper(self):
        """KIS_IS_PAPER 기본값은 True (모의투자)."""
        cfg = Config()
        assert cfg.KIS_IS_PAPER is True

    def test_default_live_trading_disabled(self):
        """LIVE_TRADING_ENABLED 기본값은 False."""
        cfg = Config()
        assert cfg.LIVE_TRADING_ENABLED is False

    @patch.dict(os.environ, {"KIS_APP_KEY": "test_key"})
    def test_kis_app_key_from_env(self):
        """환경변수에서 KIS_APP_KEY를 로드한다."""
        cfg = Config()
        assert cfg.KIS_APP_KEY == "test_key"

    @patch.dict(os.environ, {"KIS_IS_PAPER": "false"})
    def test_kis_is_paper_false(self):
        """KIS_IS_PAPER=false이면 실전 모드."""
        cfg = Config()
        assert cfg.KIS_IS_PAPER is False


class TestTradingLimits:
    """매매 한도 설정 테스트."""

    def test_default_max_daily_orders(self):
        """MAX_DAILY_ORDERS 기본값은 50."""
        cfg = Config()
        assert cfg.MAX_DAILY_ORDERS == 50

    def test_default_max_daily_amount(self):
        """MAX_DAILY_AMOUNT 기본값은 50,000,000."""
        cfg = Config()
        assert cfg.MAX_DAILY_AMOUNT == 50_000_000

    @patch.dict(os.environ, {"MAX_DAILY_ORDERS": "100"})
    def test_custom_max_daily_orders(self):
        """환경변수로 MAX_DAILY_ORDERS를 오버라이드한다."""
        cfg = Config()
        assert cfg.MAX_DAILY_ORDERS == 100


class TestStrategyConfig:
    """전략 설정 테스트."""

    def test_default_strategy_allocations(self):
        """STRATEGY_ALLOCATIONS 기본값."""
        cfg = Config()
        assert isinstance(cfg.STRATEGY_ALLOCATIONS, dict)
        assert "topdown_etf" in cfg.STRATEGY_ALLOCATIONS

    @patch.dict(os.environ, {
        "STRATEGY_ALLOCATIONS": '{"momentum":0.5,"value":0.5}',
    })
    def test_custom_strategy_allocations(self):
        """환경변수에서 JSON으로 전략 배분을 오버라이드한다."""
        cfg = Config()
        assert cfg.STRATEGY_ALLOCATIONS == {"momentum": 0.5, "value": 0.5}
