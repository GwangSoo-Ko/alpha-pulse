from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.content.agents.topic_classifier import VALID_TOPICS, TopicClassifier


def test_valid_topics_defined():
    assert "us_stock" in VALID_TOPICS
    assert "kr_stock" in VALID_TOPICS
    assert "forex" in VALID_TOPICS
    assert "bond" in VALID_TOPICS
    assert "commodity" in VALID_TOPICS


def test_parse_topics_valid():
    tc = TopicClassifier(api_key="test")
    result = tc._parse_topics('["us_stock", "bond"]')
    assert result == ["us_stock", "bond"]


def test_parse_topics_filters_invalid():
    tc = TopicClassifier(api_key="test")
    result = tc._parse_topics('["us_stock", "invalid_topic", "forex"]')
    assert result == ["us_stock", "forex"]


def test_parse_topics_from_text():
    tc = TopicClassifier(api_key="test")
    # When LLM returns topics embedded in text
    result = tc._parse_topics('Based on analysis: ["kr_stock", "commodity"]')
    assert result == ["kr_stock", "commodity"]


def test_parse_topics_empty():
    tc = TopicClassifier(api_key="test")
    result = tc._parse_topics("no valid json here")
    assert result == []


def test_parse_topics_dedup():
    tc = TopicClassifier(api_key="test")
    result = tc._parse_topics('["us_stock", "us_stock", "bond"]')
    assert result == ["us_stock", "bond"]


@pytest.mark.asyncio
async def test_classify_success():
    tc = TopicClassifier(api_key="test")
    with patch.object(tc, "_call_llm", new_callable=AsyncMock, return_value='["us_stock", "bond"]'):
        topics = await tc.classify("미국 금리 인상 전망", "연준이 금리를 인상할 것으로...")
        assert "us_stock" in topics
        assert "bond" in topics


@pytest.mark.asyncio
async def test_classify_fallback_on_failure():
    tc = TopicClassifier(api_key="test")
    with patch.object(tc, "_call_llm", new_callable=AsyncMock, side_effect=Exception("API error")):
        topics = await tc.classify("경제 뉴스", "내용")
        assert isinstance(topics, list)
        # Should return all topics as fallback
        assert len(topics) == len(VALID_TOPICS)
