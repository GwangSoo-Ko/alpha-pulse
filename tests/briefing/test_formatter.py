from alphapulse.briefing.formatter import BriefingFormatter


def test_format_quantitative_report():
    pulse_result = {
        "date": "20260323", "score": -63,
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


def test_telegram_message_length():
    formatter = BriefingFormatter()
    pulse_result = {
        "date": "20260323", "score": -63, "signal": "강한 매도",
        "indicator_scores": {f"ind_{i}": i for i in range(10)},
        "details": {},
    }
    html = formatter.format_quantitative(pulse_result)
    assert len(html) < 8192
