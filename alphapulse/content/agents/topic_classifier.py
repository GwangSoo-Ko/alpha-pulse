import asyncio
import json
import logging
import re

from google import genai

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_config = Config()

VALID_TOPICS = ["us_stock", "kr_stock", "forex", "bond", "commodity"]

TOPIC_LABELS = {
    "us_stock": "미국 주식/경제",
    "kr_stock": "한국 주식/경제",
    "forex": "외환/환율",
    "bond": "채권/금리",
    "commodity": "원자재/에너지",
}

CLASSIFIER_PROMPT = """당신은 금융·경제 콘텐츠 주제 분류 전문가입니다.
아래 블로그 글의 제목과 내용을 분석하여, 관련된 전문 분야를 모두 선택하세요.

## 분류 카테고리
- us_stock: 미국 주식, 미국 경제, 연준(Fed), 미국 기업, 나스닥, S&P500
- kr_stock: 한국 주식, 한국 경제, 한국은행, 코스피, 코스닥, 한국 기업
- forex: 외환, 환율, 달러, 엔화, 위안화, 캐리 트레이드
- bond: 채권, 금리, 국채, 회사채, 수익률 곡선
- commodity: 원자재, 원유, 금, 은, 구리, 천연가스, 에너지

## 규칙
- 관련된 카테고리를 1~5개 선택
- 반드시 JSON 배열 형태로만 응답: ["us_stock", "bond"]
- 위 5개 카테고리 중에서만 선택
- 간접적으로라도 관련되면 포함 (예: "미국 금리 인상" → ["us_stock", "bond", "forex"])

## 글 제목: {title}

## 글 내용 (앞부분):
{content}

## 응답 (JSON 배열만):
"""


class TopicClassifier:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or _config.GEMINI_API_KEY
        self.model_name = model or _config.GEMINI_MODEL
        self.max_retries = _config.MAX_RETRIES
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    async def classify(self, title: str, content: str) -> list[str]:
        content_truncated = content[:5000]
        prompt = CLASSIFIER_PROMPT.format(title=title, content=content_truncated)

        for attempt in range(self.max_retries):
            try:
                response_text = await self._call_llm(prompt)
                topics = self._parse_topics(response_text)
                if topics:
                    logger.info(f"주제 분류 결과: {topics}")
                    return topics
            except Exception as e:
                logger.warning(f"주제 분류 실패 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)

        logger.warning("주제 분류 실패, 모든 전문가에게 분석 위임")
        return list(VALID_TOPICS)

    async def _call_llm(self, prompt: str) -> str:
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
        )
        return response.text

    def _parse_topics(self, text: str) -> list[str]:
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                seen = set()
                result = []
                for t in parsed:
                    if isinstance(t, str) and t in VALID_TOPICS and t not in seen:
                        result.append(t)
                        seen.add(t)
                return result
        except (json.JSONDecodeError, TypeError):
            pass
        return []
