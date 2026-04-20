from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.content.agents.senior_analyst import SeniorAnalyst


@pytest.fixture
def senior():
    return SeniorAnalyst(api_key="test")


def test_build_prompt(senior):
    specialist_results = {
        "us_stock": "## 미국 주식 분석\n미국 시장 영향 분석",
        "bond": "## 채권 분석\n금리 영향 분석",
    }
    prompt = senior._build_prompt("미국 금리", "글 내용", specialist_results)
    assert "미국 금리" in prompt
    assert "미국 주식 분석" in prompt
    assert "채권 분석" in prompt
    assert "종합" in prompt or "자산" in prompt


def test_build_prompt_empty_specialists(senior):
    prompt = senior._build_prompt("제목", "내용", {})
    assert "제목" in prompt


def test_format_fallback_report(senior):
    specialist_results = {
        "us_stock": "## 미국 분석\n내용",
        "forex": "## 외환 분석\n내용",
    }
    report = senior._format_fallback("제목", specialist_results)
    assert "미국 분석" in report
    assert "외환 분석" in report
    assert "종합" in report or "전문가" in report


@pytest.mark.asyncio
async def test_synthesize_success(senior):
    specialist_results = {
        "us_stock": "미국 분석 결과",
        "bond": "채권 분석 결과",
    }
    final_report = "## 종합 인사이트\n최종 분석 보고서"

    with patch.object(senior, "_call_llm", new_callable=AsyncMock, return_value=final_report):
        result = await senior.synthesize("제목", "내용", specialist_results)
        assert "종합 인사이트" in result


@pytest.mark.asyncio
async def test_synthesize_fallback(senior):
    specialist_results = {
        "us_stock": "미국 분석 결과",
    }

    with patch.object(senior, "_call_llm", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await senior.synthesize("제목", "내용", specialist_results)
        assert "미국 분석 결과" in result
