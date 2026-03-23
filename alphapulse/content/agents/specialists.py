import asyncio
import logging

from google import genai

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_config = Config()

SPECIALIST_CONFIGS = {
    "us_stock": {
        "name": "미국 주식 전문가",
        "instruction": """당신은 미국 주식/경제 전문 애널리스트입니다.
아래 글을 미국 주식 시장 관점에서 분석해주세요.

분석 관점:
- 미국 주요 지수(S&P500, 나스닥, 다우) 영향
- 관련 미국 섹터/종목에 미치는 영향
- 연준(Fed) 정책과의 연관성
- 미국 경기 사이클 상 시사점
- 글로벌 자금 흐름 관점

아래 형식으로 작성:
### 관점 요약
2~3문장 요약

### 핵심 포인트
- bullet 형태로 3~5개

### 투자 시사점
- 미국 주식 투자자 관점에서의 시사점

### 리스크 요인
- 관련 리스크""",
    },
    "kr_stock": {
        "name": "국내 주식 전문가",
        "instruction": """당신은 한국 주식/경제 전문 애널리스트입니다.
아래 글을 한국 주식 시장 관점에서 분석해주세요.

분석 관점:
- 코스피/코스닥 영향
- 관련 한국 섹터/종목에 미치는 영향
- 한국은행 정책과의 연관성
- 수출/내수 경기에 미치는 영향
- 외국인/기관 수급 관점

아래 형식으로 작성:
### 관점 요약
2~3문장 요약

### 핵심 포인트
- bullet 형태로 3~5개

### 투자 시사점
- 국내 주식 투자자 관점에서의 시사점

### 리스크 요인
- 관련 리스크""",
    },
    "forex": {
        "name": "외환 전문가",
        "instruction": """당신은 외환/환율 전문 애널리스트입니다.
아래 글을 외환 시장 관점에서 분석해주세요.

분석 관점:
- 주요 통화쌍(USD/KRW, USD/JPY, EUR/USD 등) 영향
- 달러 인덱스(DXY) 방향성
- 각국 중앙은행 금리 차이와 캐리 트레이드
- 무역수지/경상수지 영향
- 외환보유고/개입 가능성

아래 형식으로 작성:
### 관점 요약
2~3문장 요약

### 핵심 포인트
- bullet 형태로 3~5개

### 투자 시사점
- 외환 관련 시사점

### 리스크 요인
- 환율 관련 리스크""",
    },
    "bond": {
        "name": "채권 전문가",
        "instruction": """당신은 채권/금리 전문 애널리스트입니다.
아래 글을 채권 시장 관점에서 분석해주세요.

분석 관점:
- 국채 수익률(미국 10년물, 한국 3년물 등) 영향
- 수익률 곡선(yield curve) 변화
- 중앙은행 기준금리 전망
- 신용 스프레드 변화
- 채권 투자 전략(듀레이션, 크레딧)

아래 형식으로 작성:
### 관점 요약
2~3문장 요약

### 핵심 포인트
- bullet 형태로 3~5개

### 투자 시사점
- 채권 투자자 관점에서의 시사점

### 리스크 요인
- 금리/채권 관련 리스크""",
    },
    "commodity": {
        "name": "원자재 전문가",
        "instruction": """당신은 원자재/에너지 전문 애널리스트입니다.
아래 글을 원자재 시장 관점에서 분석해주세요.

분석 관점:
- 원유(WTI, 브렌트) 가격 영향
- 금/은 등 귀금속 영향
- 구리/철광석 등 산업금속 영향
- 에너지 수급 변화
- 인플레이션과의 연관성

아래 형식으로 작성:
### 관점 요약
2~3문장 요약

### 핵심 포인트
- bullet 형태로 3~5개

### 투자 시사점
- 원자재 투자 관점에서의 시사점

### 리스크 요인
- 원자재 관련 리스크""",
    },
}

SPECIALIST_PROMPT_TEMPLATE = """{instruction}

## 글 제목: {title}

## 글 내용:
{content}
"""


class SpecialistAnalyst:
    def __init__(self, topic: str, name: str, instruction: str,
                 api_key: str | None = None, model: str | None = None):
        self.topic = topic
        self.name = name
        self.instruction = instruction
        self.api_key = api_key or _config.GEMINI_API_KEY
        self.model_name = model or _config.GEMINI_MODEL
        self.max_retries = _config.MAX_RETRIES
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    async def analyze(self, title: str, content: str) -> str:
        content_truncated = content[:12000]
        prompt = SPECIALIST_PROMPT_TEMPLATE.format(
            instruction=self.instruction,
            title=title,
            content=content_truncated,
        )

        for attempt in range(self.max_retries):
            try:
                result = await self._call_llm(prompt)
                logger.info(f"[{self.name}] 분석 완료")
                return result
            except Exception as e:
                logger.warning(f"[{self.name}] 분석 실패 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)

        logger.error(f"[{self.name}] 분석 최종 실패")
        return f"## {self.name} ({self.topic})\n\n(분석 실패 — API 호출 오류)\n"

    async def _call_llm(self, prompt: str) -> str:
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
        )
        return response.text


def get_specialist(topic: str, api_key: str | None = None,
                   model: str | None = None) -> "SpecialistAnalyst | None":
    config = SPECIALIST_CONFIGS.get(topic)
    if not config:
        return None
    return SpecialistAnalyst(
        topic=topic,
        name=config["name"],
        instruction=config["instruction"],
        api_key=api_key,
        model=model,
    )


def get_specialists_for_topics(topics: list[str], api_key: str | None = None,
                                model: str | None = None) -> list[SpecialistAnalyst]:
    specialists = []
    for topic in topics:
        s = get_specialist(topic, api_key=api_key, model=model)
        if s:
            specialists.append(s)
    return specialists
