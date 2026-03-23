import os
from unittest.mock import patch
from alphapulse.core.config import Config


def test_default_values():
    cfg = Config()
    assert cfg.MAX_RETRIES == 3
    assert cfg.BLOG_ID == "ranto28"
    assert cfg.BRIEFING_TIME == "08:30"


def test_env_override():
    with patch.dict(os.environ, {"MAX_RETRIES": "5", "BLOG_ID": "testblog"}):
        cfg = Config()
        assert cfg.MAX_RETRIES == 5
        assert cfg.BLOG_ID == "testblog"


def test_market_weights():
    cfg = Config()
    total = sum(cfg.WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_signal_label():
    cfg = Config()
    assert "매수" in cfg.get_signal_label(70)
    assert "중립" in cfg.get_signal_label(0)
    assert "매도" in cfg.get_signal_label(-70)


def test_data_dirs():
    cfg = Config()
    assert cfg.DATA_DIR.name == "data"
    assert cfg.CACHE_DB.name == "cache.db"
    assert cfg.HISTORY_DB.name == "history.db"


def test_gemini_model_selection():
    with patch.dict(os.environ, {"APP_ENV": "production"}):
        cfg = Config()
        assert cfg.GEMINI_MODEL == cfg.GEMINI_MODEL_PROD
    with patch.dict(os.environ, {"APP_ENV": "development"}):
        cfg = Config()
        assert cfg.GEMINI_MODEL == cfg.GEMINI_MODEL_DEV
