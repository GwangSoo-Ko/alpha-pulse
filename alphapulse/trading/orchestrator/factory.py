"""TradingEngine DI 팩토리.

Config에서 모든 협력자(broker, portfolio/risk manager, strategies 등)를
조립해 완성된 TradingEngine 인스턴스를 반환한다.
"""

from __future__ import annotations

import logging

from alphapulse.core.config import Config
from alphapulse.trading.core.audit import AuditLogger
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import TradingMode
from alphapulse.trading.data.data_provider import TradingDataProvider
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.universe import Universe
from alphapulse.trading.orchestrator.alert import TradingAlert
from alphapulse.trading.portfolio.manager import PortfolioManager
from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer
from alphapulse.trading.portfolio.position_sizer import PositionSizer
from alphapulse.trading.portfolio.rebalancer import Rebalancer
from alphapulse.trading.portfolio.store import PortfolioStore
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.var import VaRCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.ai_synthesizer import StrategyAISynthesizer
from alphapulse.trading.strategy.allocator import StrategyAllocator
from alphapulse.trading.strategy.momentum import MomentumStrategy
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy
from alphapulse.trading.strategy.value import ValueStrategy

logger = logging.getLogger(__name__)


# 한국시장 특화 기본 팩터 가중치 (momentum 25%, flow 25%, value 20%, quality 15%, growth 10%, volatility 5%)
DEFAULT_FACTOR_WEIGHTS: dict[str, float] = {
    "momentum_3m": 0.10,
    "momentum_6m": 0.15,
    "volume_trend": 0.05,
    "pbr": 0.10,
    "per": 0.10,
    "roe": 0.10,
    "debt_ratio": 0.05,
    "foreign_net": 0.15,
    "institutional_net": 0.10,
    "revenue_growth_yoy": 0.05,
    "operating_profit_growth_yoy": 0.05,
}


def build_trading_engine(
    mode: TradingMode | str,
    cfg: Config | None = None,
):
    """Config로부터 TradingEngine 그래프를 조립한다.

    Args:
        mode: 실행 모드 (PAPER/LIVE/BACKTEST).
        cfg: Config 인스턴스. None이면 새로 생성.

    Returns:
        완전히 DI된 TradingEngine.

    Raises:
        ValueError: LIVE 모드에서 safeguard 없음 등 구성 오류.
        RuntimeError: KIS 키 누락 등 런타임 오류.
    """
    # 지연 임포트: 테스트에서 engine.TradingEngine를 patch할 때,
    # factory가 모듈 로드 시점에 캐시된 참조를 사용하지 않도록 함.
    from alphapulse.trading.orchestrator.engine import TradingEngine

    if cfg is None:
        cfg = Config()

    if isinstance(mode, str):
        mode = TradingMode(mode)

    # ── 1. 데이터 레이어 ──
    store = TradingStore(str(cfg.TRADING_DB_PATH))
    universe = Universe(store=store)
    data_provider = TradingDataProvider(
        db_path=str(cfg.TRADING_DB_PATH), scheduler=None
    )

    # ── 2. 브로커 ──
    broker = _build_broker(mode, cfg)

    # ── 3. 전략 ──
    ranker = MultiFactorRanker(weights=DEFAULT_FACTOR_WEIGHTS)
    strategy_configs: dict[str, dict] = {
        "momentum": {"top_n": 20},
        "value": {"top_n": 20},
        "topdown_etf": {},
    }
    strategies: list = [
        MomentumStrategy(ranker=ranker, config=strategy_configs["momentum"]),
        ValueStrategy(ranker=ranker, config=strategy_configs["value"]),
        TopDownETFStrategy(config=strategy_configs["topdown_etf"]),
    ]

    # ── 4. 포트폴리오 + 리스크 ──
    cost_model = CostModel(
        commission_rate=cfg.BACKTEST_COMMISSION,
        tax_rate_stock=cfg.BACKTEST_TAX,
    )
    portfolio_manager = PortfolioManager(
        position_sizer=PositionSizer(),
        optimizer=PortfolioOptimizer(),
        rebalancer=Rebalancer(),
        cost_model=cost_model,
    )
    limits = RiskLimits(
        max_position_weight=cfg.MAX_POSITION_WEIGHT,
        max_drawdown_soft=cfg.MAX_DRAWDOWN_SOFT,
        max_drawdown_hard=cfg.MAX_DRAWDOWN_HARD,
    )
    risk_manager = RiskManager(
        limits=limits,
        var_calc=VaRCalculator(),
        drawdown_mgr=DrawdownManager(limits=limits),
    )

    # ── 5. 배분 + AI ──
    allocator = StrategyAllocator(base_allocations=cfg.STRATEGY_ALLOCATIONS)
    ai_synthesizer = StrategyAISynthesizer()

    # ── 6. 인프라 ──
    from alphapulse.core.notifier import TelegramNotifier

    notifier = TelegramNotifier(
        bot_token=cfg.TELEGRAM_BOT_TOKEN,
        chat_id=cfg.TELEGRAM_CHAT_ID,
    )
    alert = TradingAlert(notifier=notifier)
    audit_db_path = str(cfg.DATA_DIR / "audit.db")
    audit = AuditLogger(db_path=audit_db_path)
    portfolio_store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))

    # ── 7. LIVE 모드 안전장치 ──
    safeguard = None
    if mode == TradingMode.LIVE:
        from alphapulse.trading.broker.safeguard import TradingSafeguard

        safeguard = TradingSafeguard(
            config={
                "LIVE_TRADING_ENABLED": cfg.LIVE_TRADING_ENABLED,
                "MAX_DAILY_ORDERS": cfg.MAX_DAILY_ORDERS,
                "MAX_DAILY_AMOUNT": cfg.MAX_DAILY_AMOUNT,
            }
        )

    return TradingEngine(
        mode=mode,
        broker=broker,
        data_provider=data_provider,
        universe=universe,
        screener=ranker,
        strategies=strategies,
        allocator=allocator,
        portfolio_manager=portfolio_manager,
        risk_manager=risk_manager,
        ai_synthesizer=ai_synthesizer,
        alert=alert,
        audit=audit,
        portfolio_store=portfolio_store,
        safeguard=safeguard,
    )


def _build_broker(mode: TradingMode, cfg: Config):
    """실행 모드에 맞춰 브로커를 생성한다."""
    if not cfg.KIS_APP_KEY:
        raise RuntimeError(
            "KIS_APP_KEY가 설정되지 않았습니다. .env를 확인하세요."
        )

    from alphapulse.trading.broker.kis_client import KISClient

    client = KISClient(
        app_key=cfg.KIS_APP_KEY,
        app_secret=cfg.KIS_APP_SECRET,
        account_no=cfg.KIS_ACCOUNT_NO,
        is_paper=cfg.KIS_IS_PAPER,
    )
    audit_db_path = str(cfg.DATA_DIR / "audit.db")
    audit = AuditLogger(db_path=audit_db_path)

    if mode == TradingMode.LIVE:
        from alphapulse.trading.broker.kis_broker import KISBroker

        return KISBroker(client=client, audit=audit)
    else:
        from alphapulse.trading.broker.paper_broker import PaperBroker

        return PaperBroker(client=client, audit=audit)
