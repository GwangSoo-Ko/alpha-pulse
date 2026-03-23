# AlphaPulse Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge K-Market Pulse (quantitative) and BlogPulse (qualitative) into a unified AlphaPulse platform with 3-report system (quantitative, qualitative, synthesis) and AI commentary.

**Architecture:** Monorepo with three independent pipelines — `market/` (sync, KMP migration), `content/` (async, BlogPulse migration), `briefing/` (new integration layer). Shared infrastructure in `core/` (config, notifier, storage). Click-based CLI with subcommand groups.

**Tech Stack:** Python 3.11+, click, pykrx, pandas, httpx, crawl4ai, google-adk, rich, jinja2, SQLite, Telegram Bot API, pytest

**Source PRD:** `/Users/gwangsoo/alpha-pulse/AlphaPulse-PRD.md`
**Source KMP:** `/Users/gwangsoo/k-market-pulse/`
**Source BlogPulse:** `/Users/gwangsoo/publish-insight-report/`

---

## File Structure Overview

```
alphapulse/
├── pyproject.toml
├── .env.example
├── alphapulse/
│   ├── __init__.py
│   ├── cli.py                              # click group: ap {market,content,briefing,commentary,cache}
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                       # Merged config from both projects
│   │   ├── notifier.py                     # TelegramNotifier (from BlogPulse)
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── cache.py                    # DataCache (from KMP)
│   │       └── history.py                  # PulseHistory (from KMP)
│   ├── market/
│   │   ├── __init__.py
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # BaseCollector + @retry
│   │   │   ├── pykrx_collector.py
│   │   │   ├── krx_scraper.py
│   │   │   ├── fdr_collector.py
│   │   │   ├── fred_collector.py
│   │   │   └── investing_scraper.py
│   │   ├── analyzers/
│   │   │   ├── __init__.py
│   │   │   ├── investor_flow.py
│   │   │   ├── program_trade.py
│   │   │   ├── market_breadth.py
│   │   │   ├── fund_flow.py
│   │   │   └── macro_monitor.py
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── scoring.py
│   │   │   └── signal_engine.py
│   │   └── reporters/
│   │       ├── __init__.py
│   │       ├── terminal.py
│   │       ├── html_report.py
│   │       └── templates/
│   │           └── report.html
│   ├── content/
│   │   ├── __init__.py
│   │   ├── monitor.py                      # BlogMonitor (CLI logic removed)
│   │   ├── detector.py
│   │   ├── category_filter.py
│   │   ├── crawler.py
│   │   ├── reporter.py
│   │   ├── aggregator.py
│   │   ├── channel_monitor.py
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── orchestrator.py
│   │       ├── topic_classifier.py
│   │       ├── specialists.py
│   │       └── senior_analyst.py
│   ├── briefing/
│   │   ├── __init__.py
│   │   ├── orchestrator.py                 # BriefingOrchestrator
│   │   ├── formatter.py                    # BriefingFormatter (Telegram HTML)
│   │   └── scheduler.py                    # Daemon-mode scheduler
│   └── agents/
│       ├── __init__.py
│       ├── synthesis.py                    # SeniorSynthesisAgent (종합 판단 에이전트)
│       ├── commentary.py                   # MarketCommentaryAgent (정량 데이터 해설)
│       └── tools.py                        # MarketDataTool (v1.5 placeholder)
├── tests/
│   ├── conftest.py
│   ├── core/
│   │   ├── test_config.py
│   │   ├── test_notifier.py
│   │   └── test_storage.py
│   ├── market/
│   │   ├── conftest.py
│   │   ├── test_analyzers.py
│   │   ├── test_collectors.py
│   │   ├── test_engine.py
│   │   └── test_integration.py
│   ├── content/
│   │   ├── conftest.py
│   │   ├── test_aggregator.py
│   │   ├── test_category_filter.py
│   │   ├── test_channel_integration.py
│   │   ├── test_channel_monitor.py
│   │   ├── test_crawler.py
│   │   ├── test_detector.py
│   │   ├── test_integration.py
│   │   ├── test_monitor.py
│   │   ├── test_notifier.py
│   │   ├── test_orchestrator.py
│   │   ├── test_reporter.py
│   │   ├── test_senior_analyst.py
│   │   ├── test_specialists.py
│   │   └── test_topic_classifier.py
│   ├── briefing/
│   │   ├── test_orchestrator.py
│   │   ├── test_formatter.py
│   │   └── test_scheduler.py
│   └── agents/
│       ├── test_synthesis.py
│       └── test_commentary.py
├── data/                                   # Runtime (gitignored)
├── reports/                                # BlogPulse reports (gitignored)
└── docs/
```

---

## Phase 1: Project Scaffold + Shared Infrastructure

### Task 1.1: Project Scaffold (pyproject.toml + package init)

**Files:**
- Create: `pyproject.toml`
- Create: `alphapulse/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml with merged dependencies**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "alphapulse"
version = "1.0.0"
description = "AI 기반 투자 인텔리전스 플랫폼"
requires-python = ">=3.11"
dependencies = [
    # KMP dependencies
    "pykrx>=1.0.45",
    "finance-datareader>=0.9.90",
    "pandas>=2.0",
    "numpy>=1.24",
    "requests>=2.31",
    "beautifulsoup4>=4.12",
    "fredapi>=0.5",
    "click>=8.1",
    "rich>=13.0",
    "jinja2>=3.1",
    "matplotlib>=3.7",
    # BlogPulse dependencies
    "feedparser>=6.0",
    "crawl4ai>=0.4.0",
    "httpx>=0.27",
    "certifi>=2024.0",
    "telethon>=1.36",
    "google-adk~=1.27.2",  # 호환 릴리즈 고정 (1.27.x 허용, 1.27.0 yanked 주의)
    # Shared
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-asyncio>=0.24",
]

[project.scripts]
ap = "alphapulse.cli:cli"

[tool.setuptools.packages.find]
include = ["alphapulse*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create alphapulse/__init__.py**

```python
"""AlphaPulse - AI 기반 투자 인텔리전스 플랫폼."""

__version__ = "1.0.0"
```

- [ ] **Step 3: Create .env.example**

```bash
# === 필수 ===
GEMINI_API_KEY=your-gemini-api-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# === 선택 (KMP) ===
FRED_API_KEY=your-fred-api-key

# === 선택 (Content) ===
APP_ENV=development
BLOG_ID=ranto28
TARGET_CATEGORIES=경제,주식,국제정세,사회
SKIP_UNKNOWN_CATEGORY=true
GEMINI_MODEL_DEV=gemini-3-flash-preview
GEMINI_MODEL_PROD=gemini-3.1-pro-preview
TELEGRAM_SEND_FILE=false
CHECK_INTERVAL=600
REPORTS_DIR=./reports
STATE_FILE=./data/.monitor_state.json
LOG_FILE=./alphapulse.log
MAX_RETRIES=3

# === 선택 (Telegram Channel) ===
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
CHANNEL_IDS=
AGGREGATION_WINDOW=300

# === 선택 (Briefing) ===
BRIEFING_TIME=08:30
BRIEFING_ENABLED=true
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.env
data/
reports/
*.log
*.session
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 5: Create directory structure with __init__.py files**

Create all required directories and empty `__init__.py` files:
```
alphapulse/core/__init__.py
alphapulse/core/storage/__init__.py
alphapulse/market/__init__.py
alphapulse/market/collectors/__init__.py
alphapulse/market/analyzers/__init__.py
alphapulse/market/engine/__init__.py
alphapulse/market/reporters/__init__.py
alphapulse/content/__init__.py
alphapulse/content/agents/__init__.py
alphapulse/briefing/__init__.py
alphapulse/agents/__init__.py
tests/__init__.py
tests/core/__init__.py
tests/market/__init__.py
tests/content/__init__.py
tests/briefing/__init__.py
tests/agents/__init__.py
```

- [ ] **Step 6: Install in dev mode and verify**

Run: `cd /Users/gwangsoo/alpha-pulse && pip install -e ".[dev]"`
Expected: Installation succeeds

Run: `python -c "import alphapulse; print(alphapulse.__version__)"`
Expected: `1.0.0`

- [ ] **Step 7: Init git and commit**

```bash
cd /Users/gwangsoo/alpha-pulse
git init
git add pyproject.toml alphapulse/ tests/ .env.example .gitignore docs/
git commit -m "feat: project scaffold with merged dependencies"
```

---

### Task 1.2: Unified Config (core/config.py)

**Files:**
- Create: `alphapulse/core/config.py`
- Create: `tests/core/test_config.py`
- Ref: `/Users/gwangsoo/k-market-pulse/kmp/config.py`
- Ref: `/Users/gwangsoo/publish-insight-report/naver_blog_monitor/config.py`

- [ ] **Step 1: Write config tests**

```python
# tests/core/test_config.py
import os
from unittest.mock import patch
from alphapulse.core.config import Config


def test_default_values():
    """기본값이 올바르게 설정되는지 확인."""
    cfg = Config()
    assert cfg.MAX_RETRIES == 3
    assert cfg.BLOG_ID == "ranto28"
    assert cfg.BRIEFING_TIME == "08:30"


def test_env_override():
    """환경변수로 설정값을 오버라이드할 수 있는지 확인."""
    with patch.dict(os.environ, {"MAX_RETRIES": "5", "BLOG_ID": "testblog"}):
        cfg = Config()
        assert cfg.MAX_RETRIES == 5
        assert cfg.BLOG_ID == "testblog"


def test_market_weights():
    """KMP 가중치 합계가 1.0인지 확인."""
    cfg = Config()
    total = sum(cfg.WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_signal_label():
    """점수에 따른 시그널 라벨이 올바른지 확인."""
    cfg = Config()
    assert "매수" in cfg.get_signal_label(70)
    assert "중립" in cfg.get_signal_label(0)
    assert "매도" in cfg.get_signal_label(-70)


def test_data_dirs():
    """데이터 디렉토리 경로가 올바른지 확인."""
    cfg = Config()
    assert cfg.DATA_DIR.name == "data"
    assert cfg.CACHE_DB.name == "cache.db"
    assert cfg.HISTORY_DB.name == "history.db"


def test_gemini_model_selection():
    """APP_ENV에 따라 Gemini 모델이 선택되는지 확인."""
    with patch.dict(os.environ, {"APP_ENV": "production"}):
        cfg = Config()
        assert cfg.GEMINI_MODEL == cfg.GEMINI_MODEL_PROD
    with patch.dict(os.environ, {"APP_ENV": "development"}):
        cfg = Config()
        assert cfg.GEMINI_MODEL == cfg.GEMINI_MODEL_DEV
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Config**

Create `alphapulse/core/config.py` by merging both projects' configs:
- Copy KMP's config (WEIGHTS, SIGNAL_THRESHOLDS, SIGNAL_LABELS, date utilities, paths)
- Copy BlogPulse's config (all env vars: GEMINI, TELEGRAM, BLOG, CONTENT settings)
- Add new BRIEFING_TIME, BRIEFING_ENABLED settings
- Unify shared settings (MAX_RETRIES=3, LOG_FILE=./alphapulse.log)
- Use a `Config` class with `__init__` that reads env vars via `python-dotenv`
- Include all utility functions from KMP config: `get_signal_label()`, `get_today_str()`, `get_prev_trading_day()`, `parse_date()`, `ensure_data_dir()`
- BASE_DIR should point to the alpha-pulse project root

Key: Keep KMP's `WEIGHTS`, `SIGNAL_THRESHOLDS`, `SIGNAL_LABELS` exactly as-is. Keep BlogPulse's `TARGET_CATEGORIES`, `GEMINI_MODEL` selection logic exactly as-is.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/core/config.py tests/core/test_config.py
git commit -m "feat: unified config merging KMP + BlogPulse settings"
```

---

### Task 1.3: Shared Storage (core/storage/)

**Files:**
- Create: `alphapulse/core/storage/cache.py` (copy from KMP)
- Create: `alphapulse/core/storage/history.py` (copy from KMP)
- Create: `tests/core/test_storage.py` (copy from KMP)
- Source: `/Users/gwangsoo/k-market-pulse/kmp/storage/cache.py`
- Source: `/Users/gwangsoo/k-market-pulse/kmp/storage/history.py`
- Source: `/Users/gwangsoo/k-market-pulse/tests/test_storage.py`

- [ ] **Step 1: Copy storage modules from KMP**

Copy `/Users/gwangsoo/k-market-pulse/kmp/storage/cache.py` → `alphapulse/core/storage/cache.py`
Copy `/Users/gwangsoo/k-market-pulse/kmp/storage/history.py` → `alphapulse/core/storage/history.py`

- [ ] **Step 2: Update imports in cache.py and history.py**

Change: `from kmp.config import ...` → `from alphapulse.core.config import ...`

In cache.py, replace any reference to `kmp.config.CACHE_DB` with appropriate `Config` usage.
In history.py, replace any reference to `kmp.config.HISTORY_DB` with appropriate `Config` usage.

- [ ] **Step 3: Update storage __init__.py**

```python
# alphapulse/core/storage/__init__.py
from .cache import DataCache
from .history import PulseHistory

__all__ = ["DataCache", "PulseHistory"]
```

- [ ] **Step 4: Copy and adapt storage tests**

Copy `/Users/gwangsoo/k-market-pulse/tests/test_storage.py` → `tests/core/test_storage.py`
Update all imports: `from kmp.storage` → `from alphapulse.core.storage`

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_storage.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add alphapulse/core/storage/ tests/core/test_storage.py
git commit -m "feat: migrate storage layer (DataCache + PulseHistory) from KMP"
```

---

### Task 1.4: Shared Notifier (core/notifier.py)

**Files:**
- Create: `alphapulse/core/notifier.py` (copy from BlogPulse)
- Create: `tests/core/test_notifier.py` (copy from BlogPulse)
- Source: `/Users/gwangsoo/publish-insight-report/naver_blog_monitor/notifier.py`
- Source: `/Users/gwangsoo/publish-insight-report/tests/test_notifier.py`

- [ ] **Step 1: Copy notifier from BlogPulse**

Copy `/Users/gwangsoo/publish-insight-report/naver_blog_monitor/notifier.py` → `alphapulse/core/notifier.py`

- [ ] **Step 2: Update imports**

Change: `from naver_blog_monitor.config import ...` → `from alphapulse.core.config import ...`

- [ ] **Step 3: Copy and adapt notifier tests**

Copy `/Users/gwangsoo/publish-insight-report/tests/test_notifier.py` → `tests/core/test_notifier.py`
Update all imports: `from naver_blog_monitor.notifier` → `from alphapulse.core.notifier`
Update config imports: `from naver_blog_monitor.config` → `from alphapulse.core.config`

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_notifier.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/core/notifier.py tests/core/test_notifier.py
git commit -m "feat: migrate TelegramNotifier from BlogPulse to shared core"
```

---

### Task 1.5: CLI Skeleton (cli.py)

**Files:**
- Create: `alphapulse/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI skeleton test**

```python
# tests/test_cli.py
from click.testing import CliRunner
from alphapulse.cli import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "market" in result.output
    assert "content" in result.output
    assert "briefing" in result.output


def test_market_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["market", "--help"])
    assert result.exit_code == 0


def test_content_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "--help"])
    assert result.exit_code == 0


def test_briefing_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["briefing", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CLI skeleton**

```python
# alphapulse/cli.py
"""AlphaPulse CLI - AI 기반 투자 인텔리전스 플랫폼."""

import click
from alphapulse import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ap")
@click.option("--debug/--no-debug", default=False, help="디버그 로깅")
@click.pass_context
def cli(ctx, debug):
    """AlphaPulse - AI 기반 투자 인텔리전스 플랫폼."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


@cli.group()
def market():
    """시장 정량 분석 (Market Pulse)."""
    pass


@cli.group()
def content():
    """콘텐츠 정성 분석 (Content Intelligence)."""
    pass


@cli.command()
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--daemon", is_flag=True, help="데몬 모드 (매일 자동 실행)")
@click.option("--time", "briefing_time", default=None, help="브리핑 시간 (HH:MM)")
def briefing(no_telegram, daemon, briefing_time):
    """일일 종합 브리핑 생성 + 전송."""
    click.echo("Briefing not yet implemented")


@cli.command()
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def commentary(date):
    """AI 시장 해설 생성."""
    click.echo("Commentary not yet implemented")


@cli.group()
def cache():
    """캐시 관리."""
    pass


@cache.command("clear")
def cache_clear():
    """캐시 초기화."""
    from alphapulse.core.config import Config
    from alphapulse.core.storage import DataCache
    cfg = Config()
    cache = DataCache(cfg.CACHE_DB)
    cache.clear()
    click.echo("캐시가 초기화되었습니다.")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Verify CLI works**

Run: `ap --version`
Expected: `ap, version 1.0.0`

Run: `ap --help`
Expected: Shows market, content, briefing, commentary, cache commands

- [ ] **Step 6: Commit**

```bash
git add alphapulse/cli.py tests/test_cli.py
git commit -m "feat: CLI skeleton with market/content/briefing/commentary groups"
```

---

### Task 1.6: Test Infrastructure

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/market/conftest.py`
- Create: `tests/content/conftest.py`

- [ ] **Step 1: Create root conftest.py**

```python
# tests/conftest.py
"""Shared test fixtures for AlphaPulse."""

import os
import pytest

# Ensure tests don't accidentally use real API keys
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test-chat-id")
```

- [ ] **Step 2: Commit Phase 1 complete**

```bash
git add tests/conftest.py
git commit -m "feat: test infrastructure setup - Phase 1 complete"
```

---

## Phase 2: KMP Migration

**Critical rule from PRD addendum:** Move one module at a time, test immediately. Do NOT bulk-move.

### Task 2.1: Migrate Collectors

**Files:**
- Create: `alphapulse/market/collectors/base.py` (from KMP)
- Create: `alphapulse/market/collectors/pykrx_collector.py` (from KMP)
- Create: `alphapulse/market/collectors/fdr_collector.py` (from KMP)
- Create: `alphapulse/market/collectors/krx_scraper.py` (from KMP)
- Create: `alphapulse/market/collectors/fred_collector.py` (from KMP)
- Create: `alphapulse/market/collectors/investing_scraper.py` (from KMP)
- Create: `tests/market/test_collectors.py` (from KMP)
- Source: `/Users/gwangsoo/k-market-pulse/kmp/collectors/`
- Source: `/Users/gwangsoo/k-market-pulse/tests/test_collectors.py`

- [ ] **Step 1: Copy base.py first**

Copy `kmp/collectors/base.py` → `alphapulse/market/collectors/base.py`
Update import: `from kmp.config import MAX_RETRIES, RETRY_DELAY` → `from alphapulse.core.config import Config`
Adjust `@retry` decorator and `BaseCollector` to use Config instance or module-level config.

- [ ] **Step 2: Copy all 5 concrete collectors**

For each collector file, copy and update ALL imports:
- `from kmp.collectors.base import` → `from alphapulse.market.collectors.base import`
- `from kmp.config import` → `from alphapulse.core.config import`
- Any other `kmp.` imports → `alphapulse.` equivalent

- [ ] **Step 3: Update collectors __init__.py**

```python
# alphapulse/market/collectors/__init__.py
from .base import BaseCollector, retry
from .fdr_collector import FdrCollector
from .fred_collector import FredCollector
from .krx_scraper import KrxScraper
from .pykrx_collector import PykrxCollector
from .investing_scraper import InvestingScraper

__all__ = [
    "BaseCollector",
    "retry",
    "FdrCollector",
    "FredCollector",
    "KrxScraper",
    "PykrxCollector",
    "InvestingScraper",
]
```

- [ ] **Step 4: Copy and adapt collector tests**

Copy `tests/test_collectors.py` → `tests/market/test_collectors.py`
Update ALL imports:
- `from kmp.collectors` → `from alphapulse.market.collectors`
- `from kmp.config` → `from alphapulse.core.config`

- [ ] **Step 5: Run collector tests**

Run: `pytest tests/market/test_collectors.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add alphapulse/market/collectors/ tests/market/test_collectors.py
git commit -m "feat: migrate KMP collectors (5 collectors + base)"
```

---

### Task 2.2: Migrate Analyzers

**Files:**
- Create: `alphapulse/market/analyzers/*.py` (5 analyzers from KMP)
- Create: `tests/market/test_analyzers.py` (from KMP)
- Source: `/Users/gwangsoo/k-market-pulse/kmp/analyzers/`
- Source: `/Users/gwangsoo/k-market-pulse/tests/test_analyzers.py`

- [ ] **Step 1: Copy all 5 analyzer files**

Copy each file from `kmp/analyzers/` → `alphapulse/market/analyzers/`
- `investor_flow.py`, `program_trade.py`, `market_breadth.py`, `fund_flow.py`, `macro_monitor.py`
Update imports: `from kmp.config import` → `from alphapulse.core.config import`

- [ ] **Step 2: Update analyzers __init__.py**

```python
# alphapulse/market/analyzers/__init__.py
from .investor_flow import InvestorFlowAnalyzer
from .program_trade import ProgramTradeAnalyzer
from .market_breadth import MarketBreadthAnalyzer
from .fund_flow import FundFlowAnalyzer
from .macro_monitor import MacroMonitorAnalyzer

__all__ = [
    "InvestorFlowAnalyzer",
    "ProgramTradeAnalyzer",
    "MarketBreadthAnalyzer",
    "FundFlowAnalyzer",
    "MacroMonitorAnalyzer",
]
```

- [ ] **Step 3: Copy and adapt analyzer tests**

Copy `tests/test_analyzers.py` → `tests/market/test_analyzers.py`
Update imports: `from kmp.analyzers` → `from alphapulse.market.analyzers`

- [ ] **Step 4: Run analyzer tests**

Run: `pytest tests/market/test_analyzers.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/market/analyzers/ tests/market/test_analyzers.py
git commit -m "feat: migrate KMP analyzers (5 analyzers)"
```

---

### Task 2.3: Migrate Engine

**Files:**
- Create: `alphapulse/market/engine/scoring.py` (from KMP)
- Create: `alphapulse/market/engine/signal_engine.py` (from KMP)
- Create: `tests/market/test_engine.py` (from KMP)
- Source: `/Users/gwangsoo/k-market-pulse/kmp/engine/`
- Source: `/Users/gwangsoo/k-market-pulse/tests/test_engine.py`

- [ ] **Step 1: Copy engine files**

Copy `kmp/engine/scoring.py` → `alphapulse/market/engine/scoring.py`
Copy `kmp/engine/signal_engine.py` → `alphapulse/market/engine/signal_engine.py`

Update ALL imports in signal_engine.py:
- `from kmp.collectors` → `from alphapulse.market.collectors`
- `from kmp.analyzers` → `from alphapulse.market.analyzers`
- `from kmp.engine.scoring` → `from alphapulse.market.engine.scoring`
- `from kmp.storage` → `from alphapulse.core.storage`
- `from kmp.config` → `from alphapulse.core.config`

- [ ] **Step 2: Copy and adapt engine tests**

Copy `tests/test_engine.py` → `tests/market/test_engine.py`
Update imports accordingly.

- [ ] **Step 3: Run engine tests**

Run: `pytest tests/market/test_engine.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add alphapulse/market/engine/ tests/market/test_engine.py
git commit -m "feat: migrate KMP engine (SignalEngine + ScoringEngine)"
```

---

### Task 2.4: Migrate Reporters

**Files:**
- Create: `alphapulse/market/reporters/terminal.py` (from KMP)
- Create: `alphapulse/market/reporters/html_report.py` (from KMP)
- Create: `alphapulse/market/reporters/templates/report.html` (from KMP)
- Source: `/Users/gwangsoo/k-market-pulse/kmp/reporters/`

- [ ] **Step 1: Copy reporter files and template**

Copy `kmp/reporters/terminal.py` → `alphapulse/market/reporters/terminal.py`
Copy `kmp/reporters/html_report.py` → `alphapulse/market/reporters/html_report.py`
Copy `kmp/reporters/templates/report.html` → `alphapulse/market/reporters/templates/report.html`

Update imports:
- `from kmp.config import` → `from alphapulse.core.config import`
- Any template path references to use the new location

- [ ] **Step 2: Commit**

```bash
git add alphapulse/market/reporters/
git commit -m "feat: migrate KMP reporters (terminal + HTML)"
```

---

### Task 2.5: Wire Market CLI Commands

**Files:**
- Modify: `alphapulse/cli.py`
- Source: `/Users/gwangsoo/k-market-pulse/kmp/cli.py`

- [ ] **Step 1: Copy all market subcommands from KMP CLI**

Read `/Users/gwangsoo/k-market-pulse/kmp/cli.py` and add each command to the `market` group in `alphapulse/cli.py`:
- `pulse`, `investor`, `program`, `sector`, `macro`, `fund`, `report`, `history`

**CLI 옵션 확인 (PRD §8 준수):**
- `ap market pulse` 에 `--date DATE` + `--period {daily,weekly,monthly}` 옵션 반드시 포함
- `ap market report` 에 `--date DATE` + `--output FILE` (default: report.html) 옵션 반드시 포함
- KMP CLI에 이미 있으면 그대로 복사, 없으면 추가

Update all imports inside the commands:
- `from kmp.engine.signal_engine import SignalEngine` → `from alphapulse.market.engine.signal_engine import SignalEngine`
- `from kmp.reporters.terminal import ...` → `from alphapulse.market.reporters.terminal import ...`
- `from kmp.reporters.html_report import ...` → `from alphapulse.market.reporters.html_report import ...`
- `from kmp.storage import ...` → `from alphapulse.core.storage import ...`

- [ ] **Step 2: Copy and adapt KMP integration tests**

Copy `tests/test_integration.py` → `tests/market/test_integration.py`
Update all imports.

Copy KMP `tests/conftest.py` fixtures → `tests/market/conftest.py`
Update all imports.

- [ ] **Step 3: Run ALL market tests**

Run: `pytest tests/market/ -v`
Expected: All KMP tests PASS

- [ ] **Step 4: Verify CLI commands work**

Run: `ap market --help`
Expected: Shows pulse, investor, program, sector, macro, fund, report, history commands

- [ ] **Step 5: Phase Gate 검증 (PRD 추가사항 #7 — 가장 중요)**

`ap market pulse`가 기존 KMP의 `kmp pulse`와 동일한 출력을 내는지 반드시 확인.
실패하면 Phase 3으로 넘어가지 않는다.

Run: `ap market pulse --date 2026-03-21`
Expected: Market Pulse Score + 10개 지표 점수 출력 (KMP와 동일)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/cli.py tests/market/
git commit -m "feat: wire market CLI commands - KMP migration complete (Phase 2)"
```

---

## Phase 3: BlogPulse Migration

### Task 3.1: Migrate Content Agents

**Files:**
- Create: `alphapulse/content/agents/orchestrator.py`
- Create: `alphapulse/content/agents/topic_classifier.py`
- Create: `alphapulse/content/agents/specialists.py`
- Create: `alphapulse/content/agents/senior_analyst.py`
- Source: `/Users/gwangsoo/publish-insight-report/naver_blog_monitor/agents/`

- [ ] **Step 1: Copy all agent files**

Copy each file from `naver_blog_monitor/agents/` → `alphapulse/content/agents/`

Update ALL imports in each file:
- `from naver_blog_monitor.config import` → `from alphapulse.core.config import`
- `from naver_blog_monitor.agents.topic_classifier import` → `from alphapulse.content.agents.topic_classifier import`
- `from naver_blog_monitor.agents.specialists import` → `from alphapulse.content.agents.specialists import`
- `from naver_blog_monitor.agents.senior_analyst import` → `from alphapulse.content.agents.senior_analyst import`

- [ ] **Step 2: Update agents __init__.py**

```python
# alphapulse/content/agents/__init__.py
from .orchestrator import AnalysisOrchestrator

__all__ = ["AnalysisOrchestrator"]
```

- [ ] **Step 3: Copy and adapt agent tests**

Copy from `tests/`:
- `test_orchestrator.py` → `tests/content/test_orchestrator.py`
- `test_topic_classifier.py` → `tests/content/test_topic_classifier.py`
- `test_specialists.py` → `tests/content/test_specialists.py`
- `test_senior_analyst.py` → `tests/content/test_senior_analyst.py`

Update all imports in each test file.

- [ ] **Step 4: Run agent tests**

Run: `pytest tests/content/test_orchestrator.py tests/content/test_topic_classifier.py tests/content/test_specialists.py tests/content/test_senior_analyst.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/content/agents/ tests/content/test_orchestrator.py tests/content/test_topic_classifier.py tests/content/test_specialists.py tests/content/test_senior_analyst.py
git commit -m "feat: migrate BlogPulse multi-agent pipeline"
```

---

### Task 3.2: Migrate Content Modules

**Files:**
- Create: `alphapulse/content/detector.py`
- Create: `alphapulse/content/category_filter.py`
- Create: `alphapulse/content/crawler.py`
- Create: `alphapulse/content/reporter.py`
- Create: `alphapulse/content/aggregator.py`
- Create: `alphapulse/content/channel_monitor.py`
- Create: `alphapulse/content/monitor.py`
- Source: `/Users/gwangsoo/publish-insight-report/naver_blog_monitor/`

- [ ] **Step 1: Copy all content module files**

Copy each file from `naver_blog_monitor/` → `alphapulse/content/`:
- `detector.py`, `category_filter.py`, `crawler.py`, `reporter.py`, `aggregator.py`, `channel_monitor.py`

Update ALL imports in each file:
- `from naver_blog_monitor.config import` → `from alphapulse.core.config import`
- `from naver_blog_monitor.agents import` → `from alphapulse.content.agents import`
- `from naver_blog_monitor.notifier import` → `from alphapulse.core.notifier import`
- `from naver_blog_monitor.X import` → `from alphapulse.content.X import`

- [ ] **Step 2: Copy and adapt monitor.py (strip CLI logic)**

Copy `naver_blog_monitor/monitor.py` → `alphapulse/content/monitor.py`

Remove the `parse_args()`, `main()`, and `if __name__ == "__main__"` sections.
Keep only the `BlogMonitor` class with `run_once()`, `run_daemon()`, `_process_post()`.
Update all imports to use `alphapulse.*`.

- [ ] **Step 3: Update content __init__.py**

```python
# alphapulse/content/__init__.py
from .monitor import BlogMonitor

__all__ = ["BlogMonitor"]
```

- [ ] **Step 4: Create tests/content/conftest.py**

Copy BlogPulse의 테스트 fixture들을 `tests/content/conftest.py`로 복사.
Update all imports from `naver_blog_monitor.*` → `alphapulse.*`.

- [ ] **Step 5: Copy and adapt all content tests**

Copy each test file from BlogPulse `tests/` → `tests/content/`:
- `test_detector.py`, `test_category_filter.py`, `test_crawler.py`, `test_reporter.py`
- `test_aggregator.py`, `test_channel_monitor.py`, `test_channel_integration.py`
- `test_monitor.py`, `test_integration.py`

Update ALL imports in each test file.

- [ ] **Step 6: Run ALL content tests**

Run: `pytest tests/content/ -v`
Expected: All PASS

- [ ] **Step 7: Phase Gate 검증 (PRD 추가사항 #7)**

BlogPulse 기능이 독립적으로 동작하는지 반드시 확인.
실패하면 Phase 4로 넘어가지 않는다.

Run: `ap content monitor --force-latest 1 --no-telegram`
Expected: 블로그 최근 1개 글 처리 (RSS 감지 + 분석), 텔레그램 미전송

- [ ] **Step 8: Commit**

```bash
git add alphapulse/content/ tests/content/
git commit -m "feat: migrate BlogPulse content modules - Phase 3 complete"
```

---

### Task 3.3: Wire Content CLI Commands

**Files:**
- Modify: `alphapulse/cli.py`

- [ ] **Step 1: Add content subcommands to CLI**

Add to the `content` group in `alphapulse/cli.py`:

```python
@content.command("monitor")
@click.option("--daemon", is_flag=True, help="데몬 모드")
@click.option("--interval", type=int, default=None, help="체크 주기 (초)")
@click.option("--force-latest", type=int, default=0, help="최근 N개 강제 처리")
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--blog-only", is_flag=True, help="블로그만 모니터링")
@click.option("--channel-only", is_flag=True, help="채널만 모니터링")
def content_monitor(daemon, interval, force_latest, no_telegram, blog_only, channel_only):
    """블로그/채널 콘텐츠 모니터링."""
    import asyncio
    from alphapulse.content.monitor import BlogMonitor

    from alphapulse.core.config import Config
    cfg = Config()
    monitor = BlogMonitor()
    if daemon:
        asyncio.run(monitor.run_daemon(
            interval=interval or cfg.CHECK_INTERVAL,
            send_telegram=not no_telegram,
        ))
    else:
        asyncio.run(monitor.run_once(
            force_latest=force_latest,
            send_telegram=not no_telegram,
        ))


@content.command("test-telegram")
def content_test_telegram():
    """텔레그램 연결 테스트."""
    import asyncio
    from alphapulse.core.notifier import TelegramNotifier

    notifier = TelegramNotifier()
    asyncio.run(notifier.send_test())


@content.command("list-channels")
def content_list_channels():
    """구독 텔레그램 채널 목록."""
    from alphapulse.core.config import Config
    cfg = Config()
    if cfg.CHANNEL_IDS:
        for ch in cfg.CHANNEL_IDS:
            click.echo(f"  - {ch}")
    else:
        click.echo("구독 중인 채널이 없습니다. CHANNEL_IDS 환경변수를 설정하세요.")
```

- [ ] **Step 2: Verify CLI works**

Run: `ap content --help`
Expected: Shows monitor, test-telegram, list-channels commands

- [ ] **Step 3: Commit**

```bash
git add alphapulse/cli.py
git commit -m "feat: wire content CLI commands"
```

---

## Phase 4: Daily Briefing

### Task 4.1: BriefingOrchestrator

**Files:**
- Create: `alphapulse/briefing/orchestrator.py`
- Create: `tests/briefing/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator tests**

```python
# tests/briefing/test_orchestrator.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from alphapulse.briefing.orchestrator import BriefingOrchestrator


@pytest.fixture
def mock_pulse_result():
    return {
        "date": "20260323",
        "period": "daily",
        "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100,
            "global_market": -47,
            "sector_momentum": -100,
            "program_trade": -100,
            "exchange_rate": -22,
            "vkospi": -10,
            "adr_volume": -93,
            "spot_futures_align": -100,
            "interest_rate_diff": -19,
            "fund_flow": 50,
        },
        "details": {},
    }


def test_orchestrator_init():
    orch = BriefingOrchestrator()
    assert orch is not None


@patch("alphapulse.briefing.orchestrator.SignalEngine")
def test_run_quantitative(mock_engine_cls, mock_pulse_result):
    mock_engine = MagicMock()
    mock_engine.run.return_value = mock_pulse_result
    mock_engine_cls.return_value = mock_engine

    orch = BriefingOrchestrator()
    result = orch.run_quantitative()
    assert result["score"] == -63
    mock_engine.run.assert_called_once()


def test_collect_recent_content(tmp_path):
    # Create a fake report file
    report = tmp_path / "20260323_150000_경제_test.md"
    report.write_text("---\ntitle: Test\n---\n## 핵심 요약\nTest summary content")

    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    summaries = orch.collect_recent_content(hours=24)
    assert len(summaries) >= 1


def test_collect_recent_content_empty(tmp_path):
    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    summaries = orch.collect_recent_content(hours=24)
    assert summaries == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/briefing/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement BriefingOrchestrator**

```python
# alphapulse/briefing/orchestrator.py
"""일일 브리핑 파이프라인 조율."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from alphapulse.core.config import Config
from alphapulse.market.engine.signal_engine import SignalEngine
from alphapulse.core.storage import DataCache, PulseHistory

logger = logging.getLogger(__name__)


class BriefingOrchestrator:
    """정량 + 정성 + AI 해설을 조합하여 일일 브리핑을 생성한다."""

    def __init__(self, reports_dir: str | None = None):
        self.config = Config()
        self.reports_dir = Path(reports_dir or self.config.REPORTS_DIR)
        self.cache = DataCache(self.config.CACHE_DB)
        self.history = PulseHistory(self.config.HISTORY_DB)

    def run_quantitative(self, date: str | None = None) -> dict:
        """정량 파이프라인 실행 → Market Pulse Score."""
        engine = SignalEngine(cache=self.cache, history=self.history)
        return engine.run(date=date)

    def collect_recent_content(self, hours: int = 24) -> list[str]:
        """reports/ 디렉토리에서 최근 N시간 내 정성 분석 요약을 수집."""
        if not self.reports_dir.exists():
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        summaries = []

        for md_file in sorted(self.reports_dir.glob("*.md"), reverse=True):
            # 파일 수정 시간 기준 필터
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            if mtime < cutoff:
                continue

            try:
                text = md_file.read_text(encoding="utf-8")
                # 핵심 요약 섹션 추출
                summary = self._extract_summary(text, md_file.name)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                logger.warning(f"리포트 읽기 실패: {md_file.name}: {e}")

        return summaries

    def _extract_summary(self, text: str, filename: str) -> str | None:
        """마크다운 리포트에서 핵심 요약 섹션을 추출."""
        lines = text.split("\n")
        in_summary = False
        summary_lines = []

        for line in lines:
            if "핵심 요약" in line or "## 핵심" in line:
                in_summary = True
                continue
            if in_summary:
                if line.startswith("## ") or line.startswith("---"):
                    break
                if line.strip():
                    summary_lines.append(line.strip())

        if summary_lines:
            return f"[{filename}] " + " ".join(summary_lines[:5])
        return None

    def run(self, date: str | None = None, send_telegram: bool = True) -> dict:
        """전체 브리핑 파이프라인 실행."""
        # [1] 정량 분석
        logger.info("정량 분석 실행 중...")
        pulse_result = self.run_quantitative(date)

        # [2] 최근 정성 분석 수집
        logger.info("최근 정성 분석 수집 중...")
        content_summaries = self.collect_recent_content(hours=24)

        # [3] AI Commentary (Phase 5에서 연결)
        commentary = None

        # [4] 포맷팅 (Task 4.2에서 구현)
        briefing_data = {
            "pulse_result": pulse_result,
            "content_summaries": content_summaries,
            "commentary": commentary,
            "generated_at": datetime.now().isoformat(),
        }

        return briefing_data
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/briefing/test_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/briefing/orchestrator.py tests/briefing/test_orchestrator.py
git commit -m "feat: BriefingOrchestrator - quantitative pipeline + content collection"
```

---

### Task 4.2: BriefingFormatter

**Files:**
- Create: `alphapulse/briefing/formatter.py`
- Create: `tests/briefing/test_formatter.py`

- [ ] **Step 1: Write formatter tests**

```python
# tests/briefing/test_formatter.py
from alphapulse.briefing.formatter import BriefingFormatter


def test_format_quantitative_report():
    pulse_result = {
        "date": "20260323",
        "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100,
            "global_market": -47,
            "sector_momentum": -100,
            "program_trade": -100,
            "exchange_rate": -22,
            "vkospi": -10,
            "adr_volume": -93,
            "spot_futures_align": -100,
            "interest_rate_diff": -19,
            "fund_flow": 50,
        },
        "details": {},
    }
    formatter = BriefingFormatter()
    html = formatter.format_quantitative(pulse_result)
    assert "정량 리포트" in html
    assert "-63" in html
    assert "강한 매도" in html


def test_format_synthesis_report():
    formatter = BriefingFormatter()
    html = formatter.format_synthesis(
        pulse_result={"score": -63, "signal": "강한 매도", "date": "20260323",
                      "indicator_scores": {}, "details": {}},
        content_summaries=["[메르] 트럼프 관세 분석"],
        commentary="외국인 매도 심화로 방어적 전략 권고",
    )
    assert "종합 리포트" in html
    assert "트럼프 관세" in html
    assert "방어적 전략" in html


def test_format_synthesis_no_content():
    formatter = BriefingFormatter()
    html = formatter.format_synthesis(
        pulse_result={"score": 35, "signal": "매수 우위", "date": "20260323",
                      "indicator_scores": {}, "details": {}},
        content_summaries=[],
        commentary="시장 전반적으로 양호한 흐름",
    )
    assert "종합 리포트" in html
    assert "정성 분석 없음" in html or "최근 콘텐츠 분석 없음" in html


def test_telegram_message_length():
    """텔레그램 메시지 4096자 제한 확인."""
    formatter = BriefingFormatter()
    pulse_result = {
        "date": "20260323", "score": -63, "signal": "강한 매도",
        "indicator_scores": {f"ind_{i}": i for i in range(10)},
        "details": {},
    }
    html = formatter.format_quantitative(pulse_result)
    # 메시지가 너무 길면 split 필요
    assert len(html) < 8192  # 2 messages max
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/briefing/test_formatter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement BriefingFormatter**

```python
# alphapulse/briefing/formatter.py
"""브리핑 메시지 포맷팅 (Telegram HTML)."""

from datetime import datetime
from alphapulse.core.constants import INDICATOR_NAMES


class BriefingFormatter:
    """브리핑 데이터를 Telegram HTML 메시지로 변환."""

    def _score_emoji(self, score: float) -> str:
        if score >= 60:
            return "🟢"
        elif score >= 20:
            return "🔵"
        elif score >= -19:
            return "⚪"
        elif score >= -59:
            return "🟠"
        else:
            return "🔴"

    def _format_date(self, date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            return f"{dt.strftime('%Y-%m-%d')} ({weekdays[dt.weekday()]})"
        except (ValueError, TypeError):
            return date_str

    def format_quantitative(self, pulse_result: dict) -> str:
        """정량 리포트 HTML 포맷팅."""
        score = pulse_result["score"]
        signal = pulse_result["signal"]
        date_str = self._format_date(pulse_result.get("date", ""))
        indicator_scores = pulse_result.get("indicator_scores", {})

        lines = [
            f"<b>📊 AlphaPulse 정량 리포트 — {date_str}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Market Pulse Score: {score:+.0f} ({signal})</b>",
            "대상: KOSPI/KOSDAQ (한국시장)",
            "",
        ]

        for key, name in INDICATOR_NAMES.items():
            s = indicator_scores.get(key)
            if s is not None:
                emoji = self._score_emoji(s)
                lines.append(f"{emoji} {name}: <b>{s:+.0f}</b>")

        return "\n".join(lines)

    def format_synthesis(
        self,
        pulse_result: dict,
        content_summaries: list[str],
        commentary: str | None,
    ) -> str:
        """종합 리포트 HTML 포맷팅."""
        score = pulse_result.get("score", 0)
        signal = pulse_result.get("signal", "")
        date_str = self._format_date(pulse_result.get("date", ""))

        lines = [
            f"<b>📋 AlphaPulse 종합 리포트 — {date_str}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>[종합 판단: {signal}]</b>",
            "",
        ]

        if commentary:
            lines.append(commentary)
            lines.append("")

        if content_summaries:
            lines.append("<b>[참고 정성 분석]</b>")
            for s in content_summaries[:3]:
                lines.append(f"• {s}")
        else:
            lines.append("<i>최근 콘텐츠 분석 없음 — 정량 데이터 기반 판단</i>")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/briefing/test_formatter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/briefing/formatter.py tests/briefing/test_formatter.py
git commit -m "feat: BriefingFormatter - Telegram HTML formatting for reports"
```

---

### Task 4.3: Wire Briefing CLI + Telegram Integration

**Files:**
- Modify: `alphapulse/cli.py` (update `briefing` command)
- Modify: `alphapulse/briefing/orchestrator.py` (add Telegram send)

- [ ] **Step 1: Update BriefingOrchestrator — async 메인 메서드로 전환**

**중요 (PRD 추가사항 #1): 절대 `asyncio.run()`을 중첩 호출하지 않는다.**
BriefingOrchestrator는 `async def run_async()`를 메인 메서드로 사용하고,
CLI entry point에서만 단 한 번 `asyncio.run(orch.run_async())`를 호출한다.

Add to `orchestrator.py`:
```python
import asyncio
from alphapulse.briefing.formatter import BriefingFormatter
from alphapulse.core.notifier import TelegramNotifier

async def run_async(self, date: str | None = None, send_telegram: bool = True) -> dict:
    """전체 브리핑 파이프라인 실행 (async entry point)."""
    # [1] 정량 분석 (sync — thread에서 실행)
    logger.info("정량 분석 실행 중...")
    pulse_result = await asyncio.to_thread(self.run_quantitative, date)

    # [2] 최근 정성 분석 수집
    logger.info("최근 정성 분석 수집 중...")
    content_summaries = self.collect_recent_content(hours=24)

    # [3] AI Commentary (Phase 5에서 연결)
    commentary = None

    # [4] Format
    formatter = BriefingFormatter()
    quant_msg = formatter.format_quantitative(pulse_result)
    synth_msg = formatter.format_synthesis(pulse_result, content_summaries, commentary)

    # [5] Send via Telegram (async, 단일 이벤트 루프 내)
    if send_telegram:
        notifier = TelegramNotifier()
        await notifier._send_message(quant_msg)
        await notifier._send_message(synth_msg)

    # [6] Save history
    self.history.save(pulse_result["date"], pulse_result["score"],
                      pulse_result["signal"], pulse_result["details"])

    return {
        "pulse_result": pulse_result,
        "content_summaries": content_summaries,
        "commentary": commentary,
        "generated_at": datetime.now().isoformat(),
    }

def run(self, date: str | None = None, send_telegram: bool = True) -> dict:
    """Sync wrapper — CLI에서 호출."""
    return asyncio.run(self.run_async(date=date, send_telegram=send_telegram))
```

- [ ] **Step 2: Update briefing CLI command**

```python
@cli.command()
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--daemon", is_flag=True, help="데몬 모드")
@click.option("--time", "briefing_time", default=None, help="브리핑 시간 (HH:MM)")
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def briefing(no_telegram, daemon, briefing_time, date):
    """일일 종합 브리핑 생성 + 전송."""
    from alphapulse.briefing.orchestrator import BriefingOrchestrator

    orch = BriefingOrchestrator()

    if daemon:
        from alphapulse.briefing.scheduler import run_scheduler
        run_scheduler(orch, briefing_time=briefing_time, send_telegram=not no_telegram)
    else:
        result = orch.run(date=date, send_telegram=not no_telegram)
        click.echo(f"브리핑 완료: Score {result['pulse_result']['score']:+.0f}")
```

- [ ] **Step 3: Run all briefing tests**

Run: `pytest tests/briefing/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add alphapulse/cli.py alphapulse/briefing/
git commit -m "feat: wire briefing CLI + Telegram integration"
```

---

### Task 4.4: Scheduler (Daemon Mode)

**Files:**
- Create: `alphapulse/briefing/scheduler.py`
- Create: `tests/briefing/test_scheduler.py`

- [ ] **Step 1: Write scheduler tests**

```python
# tests/briefing/test_scheduler.py
from unittest.mock import MagicMock, patch
from alphapulse.briefing.scheduler import parse_time, should_run_now


def test_parse_time():
    h, m = parse_time("08:30")
    assert h == 8
    assert m == 30


def test_parse_time_invalid():
    h, m = parse_time("invalid")
    assert h == 8
    assert m == 30  # default


def test_should_run_now():
    from datetime import time
    target = time(8, 30)
    current = time(8, 30)
    assert should_run_now(current, target, tolerance_minutes=1)

    current2 = time(9, 0)
    assert not should_run_now(current2, target, tolerance_minutes=1)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/briefing/test_scheduler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scheduler**

```python
# alphapulse/briefing/scheduler.py
"""데몬 모드 스케줄러 — 매일 지정 시간에 브리핑 실행."""

import logging
import time as time_module
from datetime import datetime, time

logger = logging.getLogger(__name__)

DEFAULT_BRIEFING_TIME = "08:30"


def parse_time(time_str: str | None) -> tuple[int, int]:
    """HH:MM 문자열을 (hour, minute) 튜플로 파싱."""
    try:
        parts = (time_str or DEFAULT_BRIEFING_TIME).split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        logger.warning(f"잘못된 시간 형식: {time_str}, 기본값 사용: {DEFAULT_BRIEFING_TIME}")
        return 8, 30


def should_run_now(current: time, target: time, tolerance_minutes: int = 1) -> bool:
    """현재 시간이 목표 시간 ± tolerance 이내인지 확인."""
    current_mins = current.hour * 60 + current.minute
    target_mins = target.hour * 60 + target.minute
    return abs(current_mins - target_mins) <= tolerance_minutes


def run_scheduler(orchestrator, briefing_time: str | None = None,
                  send_telegram: bool = True):
    """매일 지정 시간에 브리핑을 실행하는 데몬 루프."""
    hour, minute = parse_time(briefing_time)
    target = time(hour, minute)
    logger.info(f"브리핑 스케줄러 시작: 매일 {hour:02d}:{minute:02d}")

    ran_today = False

    while True:
        now = datetime.now()
        current = now.time()

        if should_run_now(current, target) and not ran_today:
            logger.info("브리핑 실행 시작")
            try:
                orchestrator.run(send_telegram=send_telegram)
                logger.info("브리핑 완료")
            except Exception as e:
                logger.error(f"브리핑 실패: {e}")
            ran_today = True
        elif not should_run_now(current, target, tolerance_minutes=5):
            ran_today = False

        time_module.sleep(30)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/briefing/test_scheduler.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/briefing/scheduler.py tests/briefing/test_scheduler.py
git commit -m "feat: briefing scheduler daemon mode - Phase 4 complete"
```

---

## Phase 5: AI Commentary

### Task 5.1: MarketCommentaryAgent

**Files:**
- Create: `alphapulse/agents/commentary.py`
- Create: `tests/agents/test_commentary.py`

- [ ] **Step 1: Write commentary agent tests**

```python
# tests/agents/test_commentary.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from alphapulse.agents.commentary import MarketCommentaryAgent


@pytest.fixture
def sample_pulse_result():
    return {
        "date": "20260323",
        "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100,
            "global_market": -47,
            "sector_momentum": -100,
            "program_trade": -100,
            "exchange_rate": -22,
            "vkospi": -10,
            "adr_volume": -93,
            "spot_futures_align": -100,
            "interest_rate_diff": -19,
            "fund_flow": 50,
        },
        "details": {
            "investor_flow": {"foreign_net": -36755, "institution_net": -38162},
        },
    }


def test_build_prompt(sample_pulse_result):
    agent = MarketCommentaryAgent()
    prompt = agent._build_prompt(sample_pulse_result, [])
    assert "-63" in prompt
    assert "강한 매도" in prompt
    assert "investor_flow" in prompt or "외국인" in prompt


def test_build_prompt_with_content(sample_pulse_result):
    agent = MarketCommentaryAgent()
    content = ["[메르] 트럼프 관세 3차 확대 시나리오 분석"]
    prompt = agent._build_prompt(sample_pulse_result, content)
    assert "트럼프 관세" in prompt


@pytest.mark.asyncio
@patch("alphapulse.agents.commentary.MarketCommentaryAgent._call_llm")
async def test_generate(mock_llm, sample_pulse_result):
    mock_llm.return_value = "외국인 대규모 매도(-3.7조)와 프로그램 순매도가 동시 출현하며 수급이 극도로 악화되었습니다."

    agent = MarketCommentaryAgent()
    result = await agent.generate(sample_pulse_result, [])
    assert "매도" in result
    assert len(result) > 50


@pytest.mark.asyncio
@patch("alphapulse.agents.commentary.MarketCommentaryAgent._call_llm")
async def test_generate_fallback_on_failure(mock_llm, sample_pulse_result):
    mock_llm.side_effect = Exception("API Error")

    agent = MarketCommentaryAgent()
    result = await agent.generate(sample_pulse_result, [])
    # Should return fallback text, not raise
    assert result is not None
    assert len(result) > 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/agents/test_commentary.py -v`
Expected: FAIL

- [ ] **Step 3: Implement MarketCommentaryAgent**

```python
# alphapulse/agents/commentary.py
"""AI 시장 해설 에이전트 — Market Pulse 데이터 기반 자연어 해설 생성."""

import asyncio
import logging
from google import genai

from alphapulse.core.config import Config
from alphapulse.core.constants import INDICATOR_NAMES

logger = logging.getLogger(__name__)

COMMENTARY_PROMPT = """당신은 20년 경력의 시니어 투자 전략가입니다.
아래 Market Pulse 데이터를 분석하여 3~5문장의 시장 해설을 작성하세요.

규칙:
1. 핵심 수치를 반드시 인용하세요 (예: "외국인 -3.7조 매도")
2. 점수가 극단적인 지표(±80 이상)에 집중하세요
3. 상충하는 신호가 있으면 명시하세요
4. 투자 방향 제안을 포함하세요
5. 한국어로 작성하세요

{content_context}

=== Market Pulse 데이터 ===
날짜: {date}
종합 점수: {score} ({signal})

지표별 점수:
{indicators}

{details_section}
"""


class MarketCommentaryAgent:
    """AI가 Market Pulse 데이터를 읽고 자연어 시장 해설을 생성."""

    def __init__(self):
        self.config = Config()
        self.client = genai.Client(api_key=self.config.GEMINI_API_KEY)

    def _build_prompt(self, pulse_result: dict, content_summaries: list[str]) -> str:
        indicators = "\n".join(
            f"  {INDICATOR_NAMES.get(k, k)}: {v:+.0f}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )

        details_lines = []
        details = pulse_result.get("details", {})
        for key, detail in details.items():
            if isinstance(detail, dict) and "details" in detail:
                details_lines.append(f"  [{INDICATOR_NAMES.get(key, key)}] {detail['details']}")

        content_context = ""
        if content_summaries:
            content_context = "=== 최근 정성 분석 ===\n" + "\n".join(
                f"• {s}" for s in content_summaries
            )

        return COMMENTARY_PROMPT.format(
            date=pulse_result.get("date", ""),
            score=pulse_result.get("score", 0),
            signal=pulse_result.get("signal", ""),
            indicators=indicators,
            details_section="\n".join(details_lines) if details_lines else "",
            content_context=content_context,
        )

    async def _call_llm(self, prompt: str) -> str:
        """LLM 호출 (sync API를 thread에서 실행하여 이벤트 루프 블로킹 방지)."""
        def _sync_call():
            response = self.client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=1024,
                    temperature=0.3,
                ),
            )
            return response.text
        return await asyncio.to_thread(_sync_call)

    async def generate(self, pulse_result: dict, content_summaries: list[str]) -> str:
        """시장 해설 생성."""
        prompt = self._build_prompt(pulse_result, content_summaries)

        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"AI Commentary 생성 실패: {e}")
            return self._fallback(pulse_result)

    def _fallback(self, pulse_result: dict) -> str:
        score = pulse_result.get("score", 0)
        signal = pulse_result.get("signal", "")
        return f"Market Pulse Score {score:+.0f} ({signal}). AI 해설 생성에 실패했습니다. 지표 상세를 직접 확인하세요."
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/agents/test_commentary.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/agents/commentary.py tests/agents/test_commentary.py
git commit -m "feat: MarketCommentaryAgent - AI market commentary generation"
```

---

### Task 5.2: SeniorSynthesisAgent (종합 판단 에이전트 — PRD §5.3, §5.4)

**Files:**
- Create: `alphapulse/agents/synthesis.py`
- Create: `alphapulse/core/constants.py`
- Create: `tests/agents/test_synthesis.py`

- [ ] **Step 1: Create shared constants**

```python
# alphapulse/core/constants.py
"""공유 상수 정의."""

INDICATOR_NAMES = {
    "investor_flow": "외국인+기관 수급",
    "spot_futures_align": "선물 베이시스",
    "program_trade": "프로그램 비차익",
    "sector_momentum": "업종 모멘텀",
    "exchange_rate": "환율 (USD/KRW)",
    "vkospi": "V-KOSPI",
    "interest_rate_diff": "한미 금리차",
    "global_market": "글로벌 시장",
    "fund_flow": "증시 자금",
    "adr_volume": "ADR + 거래량",
}
```

- [ ] **Step 2: Write SeniorSynthesisAgent tests**

```python
# tests/agents/test_synthesis.py
import pytest
from unittest.mock import patch
from alphapulse.agents.synthesis import SeniorSynthesisAgent


@pytest.fixture
def sample_pulse():
    return {
        "date": "20260323", "score": -63, "signal": "강한 매도",
        "indicator_scores": {"investor_flow": -100, "fund_flow": 50},
        "details": {},
    }


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_with_content(mock_llm, sample_pulse):
    mock_llm.return_value = "외국인 매도와 관세 이슈가 결합되어 방어적 전략이 필요합니다."
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(
        sample_pulse,
        content_summaries=["[메르] 트럼프 관세 3차 확대"],
        commentary="외국인 대규모 매도 지속",
    )
    assert "방어적" in result


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_without_content(mock_llm, sample_pulse):
    mock_llm.return_value = "정량 데이터만으로 판단: 수급 극도 악화."
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(sample_pulse, content_summaries=[], commentary="수급 악화")
    assert len(result) > 0


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_fallback(mock_llm, sample_pulse):
    mock_llm.side_effect = Exception("API Error")
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(sample_pulse, [], None)
    assert result is not None
```

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest tests/agents/test_synthesis.py -v`
Expected: FAIL

- [ ] **Step 4: Implement SeniorSynthesisAgent**

```python
# alphapulse/agents/synthesis.py
"""Senior Synthesis Agent — 정량+정성 리포트를 소스로 종합 판단."""

import asyncio
import logging
from google import genai

from alphapulse.core.config import Config
from alphapulse.core.constants import INDICATOR_NAMES

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """당신은 20년 경력의 수석 투자 전략가(Senior Synthesis Agent)입니다.
아래 정량 분석과 정성 분석을 종합하여 투자 판단을 제시하세요.

핵심 규칙:
1. 정량 데이터와 정성 분석이 모두 있으면: 맥락을 연결하여 종합 판단
2. 정성 분석이 없으면: 정량 데이터만으로 시장 해설
3. 정량/정성이 상충하면: 상충 사실을 명시하고 양쪽 근거를 제시
4. 구체적 수치를 반드시 인용
5. 투자 방향 제안 포함
6. 한국어로 작성

=== 정량 분석 (Market Pulse) ===
날짜: {date}
종합 점수: {score} ({signal})
지표:
{indicators}

{commentary_section}

{content_section}

위 데이터를 종합하여 5~8문장의 종합 판단을 작성하세요.
마지막에 한 줄 투자 제안을 포함하세요.
"""


class SeniorSynthesisAgent:
    """정량 리포트 + 정성 리포트를 소스로 참조하여 맥락 기반 종합 판단."""

    def __init__(self):
        self.config = Config()
        self.client = genai.Client(api_key=self.config.GEMINI_API_KEY)

    def _build_prompt(self, pulse_result: dict, content_summaries: list[str],
                      commentary: str | None) -> str:
        indicators = "\n".join(
            f"  {INDICATOR_NAMES.get(k, k)}: {v:+.0f}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )
        commentary_section = ""
        if commentary:
            commentary_section = f"=== AI 시장 해설 ===\n{commentary}"

        content_section = ""
        if content_summaries:
            content_section = "=== 최근 정성 분석 ===\n" + "\n".join(
                f"• {s}" for s in content_summaries
            )
        else:
            content_section = "=== 정성 분석 없음 — 정량 데이터만으로 판단 ==="

        return SYNTHESIS_PROMPT.format(
            date=pulse_result.get("date", ""),
            score=pulse_result.get("score", 0),
            signal=pulse_result.get("signal", ""),
            indicators=indicators,
            commentary_section=commentary_section,
            content_section=content_section,
        )

    async def _call_llm(self, prompt: str) -> str:
        def _sync_call():
            response = self.client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.3,
                ),
            )
            return response.text
        return await asyncio.to_thread(_sync_call)

    async def synthesize(self, pulse_result: dict, content_summaries: list[str],
                         commentary: str | None) -> str:
        """종합 판단 생성."""
        prompt = self._build_prompt(pulse_result, content_summaries, commentary)
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"종합 판단 생성 실패: {e}")
            return self._fallback(pulse_result, content_summaries)

    def _fallback(self, pulse_result: dict, content_summaries: list[str]) -> str:
        score = pulse_result.get("score", 0)
        signal = pulse_result.get("signal", "")
        content_note = f" 최근 정성 분석 {len(content_summaries)}건 참고." if content_summaries else ""
        return f"Market Pulse {score:+.0f} ({signal}).{content_note} AI 종합 판단 생성에 실패했습니다."
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/agents/test_synthesis.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add alphapulse/core/constants.py alphapulse/agents/synthesis.py tests/agents/test_synthesis.py
git commit -m "feat: SeniorSynthesisAgent + shared constants"
```

---

### Task 5.3: Integrate Commentary + Synthesis into Briefing

**Files:**
- Modify: `alphapulse/briefing/orchestrator.py`
- Create: `alphapulse/agents/tools.py` (v1.5 placeholder)

- [ ] **Step 1: Update BriefingOrchestrator.run_async() — AI Commentary 연결**

`run_async()` 메서드의 `# [3] AI Commentary` 섹션을 업데이트:

```python
# [3] AI Commentary + SeniorSynthesis (async, 같은 이벤트 루프 내)
commentary = None
try:
    from alphapulse.agents.commentary import MarketCommentaryAgent
    agent = MarketCommentaryAgent()
    commentary = await agent.generate(pulse_result, content_summaries)
except Exception as e:
    logger.warning(f"AI Commentary 생성 실패, 스킵: {e}")

synthesis = None
try:
    from alphapulse.agents.synthesis import SeniorSynthesisAgent
    synth_agent = SeniorSynthesisAgent()
    synthesis = await synth_agent.synthesize(pulse_result, content_summaries, commentary)
except Exception as e:
    logger.warning(f"종합 판단 생성 실패, 스킵: {e}")
```

**중요: 모두 `await`로 호출. `asyncio.run()` 절대 사용하지 않는다.**

- [ ] **Step 2: Create v1.5 tools placeholder**

```python
# alphapulse/agents/tools.py
"""AI 에이전트용 Market Data 접근 인터페이스.

v1.5에서 ADK FunctionTool로 확장 예정.
현재는 직접 호출 인터페이스만 제공.
"""


def get_market_pulse_score(date: str = "today") -> dict:
    """오늘의 Market Pulse Score와 10개 지표 점수를 반환."""
    from alphapulse.market.engine.signal_engine import SignalEngine
    engine = SignalEngine()
    result = engine.run(date if date != "today" else None)
    return {
        "score": result["score"],
        "signal": result["signal"],
        "indicators": result["indicator_scores"],
    }


def get_recent_content_analysis(hours: int = 24) -> list[str]:
    """최근 N시간 내 콘텐츠 분석 요약 목록."""
    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    orch = BriefingOrchestrator()
    return orch.collect_recent_content(hours=hours)


def get_pulse_history(days: int = 7) -> list[dict]:
    """최근 N일간 Market Pulse Score 이력."""
    from alphapulse.core.storage import PulseHistory
    from alphapulse.core.config import Config
    cfg = Config()
    history = PulseHistory(cfg.HISTORY_DB)
    return history.get_recent(days=days)
```

- [ ] **Step 3: Update commentary CLI command**

In `cli.py`, update the `commentary` command:
```python
@cli.command()
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def commentary(date):
    """AI 시장 해설 생성."""
    import asyncio
    from alphapulse.market.engine.signal_engine import SignalEngine
    from alphapulse.agents.commentary import MarketCommentaryAgent
    from alphapulse.briefing.orchestrator import BriefingOrchestrator

    engine = SignalEngine()
    pulse_result = engine.run(date)

    orch = BriefingOrchestrator()
    content_summaries = orch.collect_recent_content(hours=24)

    agent = MarketCommentaryAgent()
    result = asyncio.run(agent.generate(pulse_result, content_summaries))
    click.echo(result)
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/briefing/ tests/agents/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add alphapulse/briefing/orchestrator.py alphapulse/agents/tools.py alphapulse/cli.py
git commit -m "feat: integrate AI commentary into briefing pipeline - Phase 5 complete"
```

---

## Phase 6: Test + Polish

### Task 6.1: Integration Tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write E2E integration tests**

```python
# tests/test_integration.py
"""AlphaPulse 통합 테스트 — 전체 파이프라인 E2E."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner
from alphapulse.cli import cli


def test_cli_market_pulse_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["market", "pulse", "--help"])
    assert result.exit_code == 0
    assert "--date" in result.output


def test_cli_content_monitor_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "monitor", "--help"])
    assert result.exit_code == 0
    assert "--daemon" in result.output


def test_cli_briefing_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["briefing", "--help"])
    assert result.exit_code == 0


def test_cli_commentary_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["commentary", "--help"])
    assert result.exit_code == 0


def test_cli_cache_clear():
    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear"])
    assert result.exit_code == 0


@patch("alphapulse.briefing.orchestrator.SignalEngine")
def test_briefing_orchestrator_e2e(mock_engine_cls, tmp_path):
    """BriefingOrchestrator E2E — mock engine, real formatter."""
    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260323",
        "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100, "global_market": -47,
            "sector_momentum": -100, "program_trade": -100,
            "exchange_rate": -22, "vkospi": -10,
            "adr_volume": -93, "spot_futures_align": -100,
            "interest_rate_diff": -19, "fund_flow": 50,
        },
        "details": {},
    }
    mock_engine_cls.return_value = mock_engine

    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    result = orch.run(send_telegram=False)

    assert result["pulse_result"]["score"] == -63
    assert isinstance(result["content_summaries"], list)


def test_formatter_quantitative_e2e():
    """BriefingFormatter — 실제 데이터로 정량 리포트 포맷."""
    from alphapulse.briefing.formatter import BriefingFormatter
    formatter = BriefingFormatter()
    html = formatter.format_quantitative({
        "date": "20260323",
        "score": -63,
        "signal": "강한 매도",
        "indicator_scores": {
            "investor_flow": -100, "global_market": -47,
        },
        "details": {},
    })
    assert "📊" in html
    assert "정량 리포트" in html
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add E2E integration tests for full pipeline"
```

---

### Task 6.2: Full Test Suite Verification

- [ ] **Step 1: Run ALL tests together**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (target 220+)

- [ ] **Step 2: Run market tests in isolation (per PRD addendum)**

Run: `pytest tests/market/ -v`
Expected: All PASS independently

- [ ] **Step 3: Run content tests in isolation**

Run: `pytest tests/content/ -v`
Expected: All PASS independently

- [ ] **Step 4: Run coverage report**

Run: `pytest tests/ --cov=alphapulse --cov-report=term-missing`
Expected: 85%+ coverage

- [ ] **Step 5: Fix any coverage gaps if below 85%**

Review uncovered lines and add targeted tests.

---

### Task 6.3: Documentation + Final Polish

**Files:**
- Verify: `.env.example` is complete
- Create: `CLAUDE.md` (project guidance)

- [ ] **Step 1: Verify .env.example has all variables from PRD §9**

Cross-check with the PRD environment variables table. All 25+ variables should be present.

- [ ] **Step 2: Create CLAUDE.md**

```markdown
# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼.

## Quick Start

pip install -e ".[dev]"
ap --version
ap market pulse
ap briefing --no-telegram

## Architecture

- `alphapulse/market/` — 정량 분석 (KMP 마이그레이션). Sync.
- `alphapulse/content/` — 정성 분석 (BlogPulse 마이그레이션). Async.
- `alphapulse/briefing/` — 일일 브리핑 통합. Sync entry, async AI calls.
- `alphapulse/agents/` — AI 에이전트 (MarketCommentaryAgent).
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage).

## Testing

pytest tests/ -v                    # 전체
pytest tests/market/ -v             # 정량 분석만
pytest tests/content/ -v            # 정성 분석만
pytest tests/briefing/ -v           # 브리핑만

## Key Rules

- Market pipeline is SYNC (requests, pykrx). Content pipeline is ASYNC (httpx, crawl4ai).
- Never nest asyncio.run() calls.
- Config via environment variables (.env file). See .env.example.
- AI uses Google Gemini API (google-adk).
```

- [ ] **Step 3: Final commit**

```bash
git add CLAUDE.md .env.example
git commit -m "docs: add CLAUDE.md and finalize .env.example - Phase 6 complete"
```

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| **Phase 1** | 1.1 ~ 1.6 | Scaffold, config, storage, notifier, CLI skeleton |
| **Phase 2** | 2.1 ~ 2.5 | KMP full migration (collectors, analyzers, engine, reporters, CLI) + Phase Gate |
| **Phase 3** | 3.1 ~ 3.3 | BlogPulse full migration (agents, content modules, CLI) + Phase Gate |
| **Phase 4** | 4.1 ~ 4.4 | BriefingOrchestrator (async-first), Formatter, Telegram, Scheduler |
| **Phase 5** | 5.1 ~ 5.3 | MarketCommentaryAgent, SeniorSynthesisAgent, Integration |
| **Phase 6** | 6.1 ~ 6.3 | Integration tests, coverage, documentation |

**Total Tasks:** 21
**Total Tests Target:** 230+ (101 KMP + 94 BlogPulse + 35+ new)

## Key Architectural Decisions (Review Issues Fixed)

1. **Async safety:** Single `asyncio.run()` at CLI entry → `run_async()` pattern. No nested event loops.
2. **SeniorSynthesisAgent:** Separate from MarketCommentaryAgent. Commentary=정량해설, Synthesis=종합판단.
3. **Shared constants:** `INDICATOR_NAMES` in `core/constants.py` (DRY).
4. **google-adk pinned:** `~=1.0.0` (compatible release).
5. **LLM async:** `asyncio.to_thread()` for sync genai calls.
