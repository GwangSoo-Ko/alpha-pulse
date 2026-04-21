"""SignalEngine — indicator_descriptions 추출 헬퍼 검증."""
from alphapulse.market.engine.signal_engine import (
    extract_indicator_descriptions,
)


def test_extracts_details_strings_from_analyzer_results():
    """각 analyzer 결과 dict 에서 'details' 문자열만 추출."""
    analyzer_results = {
        "investor_flow": {"score": 50, "details": "외국인 +580억"},
        "vkospi": {"score": -30, "details": "V-KOSPI 22.5 (위험)"},
    }
    assert extract_indicator_descriptions(analyzer_results) == {
        "investor_flow": "외국인 +580억",
        "vkospi": "V-KOSPI 22.5 (위험)",
    }


def test_returns_none_when_details_key_missing():
    analyzer_results = {"bad": {"score": 0}}  # details 키 없음
    assert extract_indicator_descriptions(analyzer_results) == {"bad": None}


def test_returns_none_for_non_dict_value():
    analyzer_results = {"broken": None, "other": "string_not_dict"}
    assert extract_indicator_descriptions(analyzer_results) == {
        "broken": None, "other": None,
    }


def test_empty_input_returns_empty_dict():
    assert extract_indicator_descriptions({}) == {}
