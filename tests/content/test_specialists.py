from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.content.agents.specialists import (
    SPECIALIST_CONFIGS,
    get_specialist,
    get_specialists_for_topics,
)


def test_specialist_configs_all_defined():
    assert "us_stock" in SPECIALIST_CONFIGS
    assert "kr_stock" in SPECIALIST_CONFIGS
    assert "forex" in SPECIALIST_CONFIGS
    assert "bond" in SPECIALIST_CONFIGS
    assert "commodity" in SPECIALIST_CONFIGS


def test_specialist_config_has_required_fields():
    for topic, config in SPECIALIST_CONFIGS.items():
        assert "name" in config
        assert "instruction" in config
        assert len(config["instruction"]) > 50  # meaningful instruction


def test_get_specialist():
    specialist = get_specialist("us_stock", api_key="test")
    assert specialist is not None
    assert specialist.topic == "us_stock"
    assert "미국" in specialist.name


def test_get_specialist_invalid():
    specialist = get_specialist("invalid_topic", api_key="test")
    assert specialist is None


def test_get_specialists_for_topics():
    specialists = get_specialists_for_topics(["us_stock", "bond"], api_key="test")
    assert len(specialists) == 2
    topics = [s.topic for s in specialists]
    assert "us_stock" in topics
    assert "bond" in topics


def test_get_specialists_filters_invalid():
    specialists = get_specialists_for_topics(["us_stock", "invalid", "forex"], api_key="test")
    assert len(specialists) == 2


@pytest.mark.asyncio
async def test_specialist_analyze_success():
    specialist = get_specialist("us_stock", api_key="test")
    with patch.object(specialist, "_call_llm", new_callable=AsyncMock, return_value="## 미국 주식 관점 분석\n분석 내용"):
        result = await specialist.analyze("미국 금리", "연준이 금리를...")
        assert "미국 주식 관점" in result


@pytest.mark.asyncio
async def test_specialist_analyze_fallback():
    specialist = get_specialist("bond", api_key="test")
    with patch.object(specialist, "_call_llm", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await specialist.analyze("제목", "내용")
        assert "분석 실패" in result or specialist.topic in result


@pytest.mark.asyncio
async def test_parallel_analysis():
    specialists = get_specialists_for_topics(["us_stock", "forex", "bond"], api_key="test")

    for s in specialists:
        s._call_llm = AsyncMock(return_value=f"## {s.name} 분석\n분석 결과")

    import asyncio
    results = await asyncio.gather(*[s.analyze("제목", "내용") for s in specialists])
    assert len(results) == 3
    assert all(isinstance(r, str) for r in results)
