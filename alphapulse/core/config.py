"""통합 설정 관리 - KMP + BlogPulse 설정 병합"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """AlphaPulse 통합 설정 클래스.

    KMP(시장 분석)와 BlogPulse(블로그 모니터링) 설정을 하나로 통합한다.
    모든 설정은 기본값이 있으며, 환경변수 또는 .env 파일로 오버라이드 가능하다.
    """

    def __init__(self) -> None:
        # 프로젝트 경로
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.CACHE_DB = self.DATA_DIR / "cache.db"
        self.HISTORY_DB = self.DATA_DIR / "history.db"
        self.BRIEFINGS_DB = self.DATA_DIR / "briefings.db"
        self.FEEDBACK_DB = self.DATA_DIR / "feedback.db"
        self.CONTENT_SEARCH_DB = self.DATA_DIR / "content_search.db"

        # .env 파일 로드 (프로젝트 루트)
        load_dotenv(self.BASE_DIR / ".env")

        # ── 공통 설정 ──────────────────────────────────────────────
        self.MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
        self.RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "1"))  # 초
        self.LOG_FILE = os.environ.get("LOG_FILE", "./alphapulse.log")

        # ── KMP: API 키 ───────────────────────────────────────────
        self.FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

        # ── KMP: 캐시 TTL (분) ─────────────────────────────────────
        self.CACHE_TTL_INTRADAY = int(os.environ.get("CACHE_TTL_INTRADAY", "30"))
        self.CACHE_TTL_HISTORICAL = int(os.environ.get("CACHE_TTL_HISTORICAL", "0"))

        # ── KMP: 시장 구분 ─────────────────────────────────────────
        self.MARKETS = {
            "kospi": "KOSPI",
            "kosdaq": "KOSDAQ",
            "kospi200": "KOSPI200",
        }

        # ── KMP: Market Pulse Score 가중치 (합계 1.0) ──────────────
        self.WEIGHTS = {
            "investor_flow": 0.18,
            "spot_futures_align": 0.05,
            "futures_flow": 0.07,
            "program_trade": 0.08,
            "sector_momentum": 0.10,
            "exchange_rate": 0.10,
            "vkospi": 0.10,
            "interest_rate_diff": 0.05,
            "global_market": 0.13,
            "fund_flow": 0.05,
            "adr_volume": 0.09,
        }

        # ── KMP: 시황 판단 기준 ────────────────────────────────────
        self.SIGNAL_THRESHOLDS = {
            "strong_bullish": 60,
            "moderately_bullish": 20,
            "neutral_low": -19,
            "moderately_bearish": -59,
        }

        self.SIGNAL_LABELS = {
            "strong_bullish": "강한 매수 (Strong Bullish)",
            "moderately_bullish": "매수 우위 (Moderately Bullish)",
            "neutral": "중립 (Neutral)",
            "moderately_bearish": "매도 우위 (Moderately Bearish)",
            "strong_bearish": "강한 매도 (Strong Bearish)",
        }

        # ── BlogPulse: Gemini 설정 ─────────────────────────────────
        self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
        self.APP_ENV = os.environ.get("APP_ENV", "development")
        self.GEMINI_MODEL_DEV = os.environ.get("GEMINI_MODEL_DEV", "gemini-3-flash-preview")
        self.GEMINI_MODEL_PROD = os.environ.get("GEMINI_MODEL_PROD", "gemini-3.1-pro-preview")
        self.GEMINI_MODEL = (
            self.GEMINI_MODEL_PROD if self.APP_ENV == "production" else self.GEMINI_MODEL_DEV
        )

        # ── BlogPulse: Telegram 설정 ──────────────────────────────
        self.TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.TELEGRAM_SEND_FILE = (
            os.environ.get("TELEGRAM_SEND_FILE", "false").lower() == "true"
        )
        self.TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID", "")
        self.TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
        self.TELEGRAM_PHONE = os.environ.get("TELEGRAM_PHONE", "")
        self.CHANNEL_IDS = [
            c.strip()
            for c in os.environ.get("CHANNEL_IDS", "").split(",")
            if c.strip()
        ]
        self.AGGREGATION_WINDOW = int(os.environ.get("AGGREGATION_WINDOW", "300"))

        # ── BlogPulse: 블로그 모니터링 설정 ────────────────────────
        self.BLOG_ID = os.environ.get("BLOG_ID", "ranto28")
        self.TARGET_CATEGORIES = os.environ.get(
            "TARGET_CATEGORIES", "경제,주식,국제정세,사회"
        ).split(",")
        self.SKIP_UNKNOWN_CATEGORY = (
            os.environ.get("SKIP_UNKNOWN_CATEGORY", "true").lower() == "true"
        )
        self.CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "600"))
        self.REPORTS_DIR = os.environ.get("REPORTS_DIR", "./reports")
        self.STATE_FILE = os.environ.get("STATE_FILE", "./.monitor_state.json")

        # ── 신규: 브리핑 설정 ──────────────────────────────────────
        self.BRIEFING_TIME = os.environ.get("BRIEFING_TIME", "08:30")
        self.BRIEFING_ENABLED = (
            os.environ.get("BRIEFING_ENABLED", "true").lower() == "true"
        )

        # ── Feedback 설정 ────────────────────────────────────────
        self.FEEDBACK_ENABLED = os.environ.get("FEEDBACK_ENABLED", "true").lower() == "true"
        self.FEEDBACK_LOOKBACK_DAYS = int(os.environ.get("FEEDBACK_LOOKBACK_DAYS", "30"))
        self.FEEDBACK_NEWS_ENABLED = os.environ.get("FEEDBACK_NEWS_ENABLED", "true").lower() == "true"
        self.FEEDBACK_NEWS_COUNT = int(os.environ.get("FEEDBACK_NEWS_COUNT", "10"))

        # ── Trading: KIS API ─────────────────────────────────────
        self.KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
        self.KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
        self.KIS_ACCOUNT_NO = os.environ.get("KIS_ACCOUNT_NO", "")
        self.KIS_IS_PAPER = os.environ.get("KIS_IS_PAPER", "true").lower() == "true"

        # ── Trading: 안전장치 ─────────────────────────────────────
        self.LIVE_TRADING_ENABLED = (
            os.environ.get("LIVE_TRADING_ENABLED", "false").lower() == "true"
        )
        self.MAX_DAILY_ORDERS = int(os.environ.get("MAX_DAILY_ORDERS", "50"))
        self.MAX_DAILY_AMOUNT = int(os.environ.get("MAX_DAILY_AMOUNT", "50000000"))

        # ── Trading: 전략 설정 ─────────────────────────────────────
        default_alloc = '{"topdown_etf":0.3,"momentum":0.4,"value":0.3}'
        alloc_str = os.environ.get("STRATEGY_ALLOCATIONS", default_alloc)
        try:
            self.STRATEGY_ALLOCATIONS = json.loads(alloc_str)
        except (json.JSONDecodeError, TypeError):
            self.STRATEGY_ALLOCATIONS = {"topdown_etf": 0.3, "momentum": 0.4, "value": 0.3}

        self.MOMENTUM_TOP_N = int(os.environ.get("MOMENTUM_TOP_N", "20"))
        self.VALUE_TOP_N = int(os.environ.get("VALUE_TOP_N", "15"))

        # ── Trading: 데이터베이스 경로 ────────────────────────────
        self.TRADING_DB_PATH = self.DATA_DIR / "trading.db"
        self.PORTFOLIO_DB_PATH = self.DATA_DIR / "portfolio.db"
        self.BACKTEST_DB_PATH = self.DATA_DIR / "backtest.db"

        # ── Trading: 백테스트 기본값 ──────────────────────────────
        self.BACKTEST_INITIAL_CAPITAL = int(
            os.environ.get("BACKTEST_INITIAL_CAPITAL", "100000000")  # 1억
        )
        self.BACKTEST_COMMISSION = float(
            os.environ.get("BACKTEST_COMMISSION", "0.00015")  # 0.015%
        )
        self.BACKTEST_TAX = float(
            os.environ.get("BACKTEST_TAX", "0.0018")  # 0.18%
        )

        # ── Trading: Paper Broker 초기 자본 ───────────────────────
        self.PAPER_INITIAL_CAPITAL = int(
            os.environ.get("PAPER_INITIAL_CAPITAL", "100000000")  # 1억
        )

        # ── Trading: 리스크 리밋 ──────────────────────────────────
        self.MAX_POSITION_WEIGHT = float(
            os.environ.get("MAX_POSITION_WEIGHT", "0.10")  # 종목당 최대 10%
        )
        self.MAX_SECTOR_WEIGHT = float(
            os.environ.get("MAX_SECTOR_WEIGHT", "0.30")  # 섹터당 최대 30%
        )
        self.MAX_DRAWDOWN_SOFT = float(
            os.environ.get("MAX_DRAWDOWN_SOFT", "0.10")  # -10% 경고
        )
        self.MAX_DRAWDOWN_HARD = float(
            os.environ.get("MAX_DRAWDOWN_HARD", "0.15")  # -15% 강제 축소
        )
        self.MAX_DAILY_LOSS = float(
            os.environ.get("MAX_DAILY_LOSS", "0.03")  # 일간 -3% 중단
        )
        self.MIN_CASH_RATIO = float(
            os.environ.get("MIN_CASH_RATIO", "0.05")  # 최소 현금 5%
        )

        # ── Trading: 유니버스 필터 ────────────────────────────────
        self.MIN_MARKET_CAP = float(
            os.environ.get("MIN_MARKET_CAP", "100000000000")  # 1000억
        )
        self.MIN_AVG_VOLUME = float(
            os.environ.get("MIN_AVG_VOLUME", "1000000000")  # 10억원 (일평균 거래대금)
        )

        # ── Trading: AI 종합 판단 ─────────────────────────────────
        self.AI_SYNTHESIS_ENABLED = bool(self.GEMINI_API_KEY)

    # ── 유틸리티 메서드 (KMP 유래) ──────────────────────────────────

    def get_signal_label(self, score: float) -> str:
        """점수에 따른 시황 판단 라벨 반환"""
        if score >= self.SIGNAL_THRESHOLDS["strong_bullish"]:
            return self.SIGNAL_LABELS["strong_bullish"]
        elif score >= self.SIGNAL_THRESHOLDS["moderately_bullish"]:
            return self.SIGNAL_LABELS["moderately_bullish"]
        elif score >= self.SIGNAL_THRESHOLDS["neutral_low"]:
            return self.SIGNAL_LABELS["neutral"]
        elif score >= self.SIGNAL_THRESHOLDS["moderately_bearish"]:
            return self.SIGNAL_LABELS["moderately_bearish"]
        else:
            return self.SIGNAL_LABELS["strong_bearish"]

    @staticmethod
    def get_today_str() -> str:
        """오늘 날짜를 YYYYMMDD 형식으로 반환"""
        return datetime.now().strftime("%Y%m%d")

    @staticmethod
    def get_prev_trading_day(base_date: datetime | None = None) -> str:
        """직전 거래일을 YYYYMMDD 형식으로 반환.

        주말을 건너뛰어 가장 최근 거래일을 찾는다.
        - 월요일 장 전 -> 금요일
        - 토/일 -> 금요일
        - 화~금 장 전 -> 전일
        """
        if base_date is None:
            base_date = datetime.now()

        # 장 시작 전(09:00 이전)이면 전일 기준
        if base_date.hour < 9:
            base_date -= timedelta(days=1)

        # 주말 건너뛰기
        while base_date.weekday() >= 5:  # 5=토, 6=일
            base_date -= timedelta(days=1)

        return base_date.strftime("%Y%m%d")

    @staticmethod
    def get_date_str(days_ago: int = 0) -> str:
        """N일 전 날짜를 YYYYMMDD 형식으로 반환"""
        return (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")

    @staticmethod
    def parse_date(date_str: str) -> str:
        """다양한 날짜 형식을 YYYYMMDD로 변환"""
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
            except ValueError:
                continue
        raise ValueError(f"지원하지 않는 날짜 형식: {date_str}")

    def ensure_data_dir(self) -> None:
        """데이터 디렉토리 생성"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
