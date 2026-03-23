"""점수 계산 유틸리티"""

import numpy as np
from alphapulse.core.config import Config

_config = Config()


def normalize_score(value: float, min_val: float = -100, max_val: float = 100) -> float:
    """값을 -100 ~ +100 범위로 정규화"""
    return float(np.clip(value, min_val, max_val))


def calculate_weighted_score(scores: dict[str, float]) -> tuple[float, str]:
    """
    가중 합산 점수 계산

    Args:
        scores: {지표명: 개별 점수} dict. 키는 WEIGHTS 키와 매칭.
                None인 지표는 제외하고 가중치 재배분.

    Returns:
        (최종 점수, 시황 판단 라벨)
    """
    active_weights = {}
    active_scores = {}

    for key, weight in _config.WEIGHTS.items():
        if key in scores and scores[key] is not None:
            active_weights[key] = weight
            active_scores[key] = normalize_score(scores[key])

    if not active_weights:
        return 0.0, _config.get_signal_label(0)

    # 가중치 재배분 (N/A 지표 제외)
    total_weight = sum(active_weights.values())
    weighted_sum = sum(
        active_scores[key] * (active_weights[key] / total_weight)
        for key in active_scores
    )

    final_score = round(normalize_score(weighted_sum), 1)
    label = _config.get_signal_label(final_score)

    return final_score, label
