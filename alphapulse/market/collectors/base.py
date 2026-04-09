"""데이터 수집기 베이스 클래스

모든 수집기가 상속받는 기본 클래스와 재시도 데코레이터를 제공한다.
"""

import logging
import time
from abc import ABC
from functools import wraps
from typing import Any

import pandas as pd

# 기본 재시도 설정 (순환 import 방지를 위해 직접 정의)
MAX_RETRIES = 3
RETRY_DELAY = 1

logger = logging.getLogger(__name__)


def retry(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """재시도 데코레이터.

    지정된 횟수만큼 함수 호출을 재시도한다.
    마지막 시도까지 실패하면 마지막 예외를 그대로 발생시킨다.

    Args:
        max_retries: 최대 재시도 횟수.
        delay: 재시도 사이 대기 시간(초).

    Returns:
        데코레이터 함수.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"{func.__name__} 실패 "
                        f"(시도 {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            logger.error(f"{func.__name__} 최종 실패: {last_exception}")
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


class BaseCollector(ABC):
    """데이터 수집기 베이스 클래스.

    캐시 연동과 공통 유틸리티를 제공한다.
    모든 수집기는 이 클래스를 상속받아야 한다.

    Attributes:
        cache: DataCache 인스턴스. None이면 캐시를 사용하지 않는다.
        logger: 클래스별 로거 인스턴스.
    """

    def __init__(self, cache: Any | None = None) -> None:
        """BaseCollector 초기화.

        Args:
            cache: DataCache 인스턴스 (선택).
        """
        self.cache = cache
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_cached(self, key: str, ttl_minutes: int = 0) -> pd.DataFrame | None:
        """캐시에서 데이터를 조회한다.

        Args:
            key: 캐시 키.
            ttl_minutes: TTL(분). 0이면 만료되지 않는다.

        Returns:
            캐시된 DataFrame 또는 None.
        """
        if self.cache:
            return self.cache.get(key, ttl_minutes)
        return None

    def _set_cached(self, key: str, data: pd.DataFrame) -> None:
        """데이터를 캐시에 저장한다.

        Args:
            key: 캐시 키.
            data: 저장할 DataFrame.
        """
        if self.cache:
            self.cache.set(key, data)
