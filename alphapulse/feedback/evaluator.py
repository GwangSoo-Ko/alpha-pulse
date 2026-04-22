"""피드백 평가 — 적중률, 상관계수, 지표별 정확도 계산."""

import json
import logging
from typing import Any

import numpy as np

from alphapulse.core.storage.feedback import FeedbackStore

logger = logging.getLogger(__name__)


class FeedbackEvaluator:
    """과거 시그널 성과를 분석하여 적중률/상관계수를 계산."""

    def __init__(self, store: FeedbackStore | None = None, db_path=None):
        if store:
            self.store = store
        else:
            from alphapulse.core.config import Config
            cfg = Config()
            self.store = FeedbackStore(db_path or (cfg.DATA_DIR / "feedback.db"))

    def get_hit_rates(self, days: int = 30) -> dict:
        """기간별 적중률 계산."""
        records = self.store.get_recent(limit=days)
        evaluated = [r for r in records if r["hit_1d"] is not None]

        if not evaluated:
            return {
                "hit_rate_1d": 0.0, "hit_rate_3d": 0.0, "hit_rate_5d": 0.0,
                "total_evaluated": 0,
            }

        hits_1d = [r["hit_1d"] for r in evaluated if r["hit_1d"] is not None]
        hits_3d = [r["hit_3d"] for r in evaluated if r["hit_3d"] is not None]
        hits_5d = [r["hit_5d"] for r in evaluated if r["hit_5d"] is not None]

        return {
            "hit_rate_1d": round(sum(hits_1d) / len(hits_1d), 2) if hits_1d else 0.0,
            "hit_rate_3d": round(sum(hits_3d) / len(hits_3d), 2) if hits_3d else 0.0,
            "hit_rate_5d": round(sum(hits_5d) / len(hits_5d), 2) if hits_5d else 0.0,
            "total_evaluated": len(evaluated),
            "count_1d": len(hits_1d),
            "count_3d": len(hits_3d),
            "count_5d": len(hits_5d),
        }

    def get_indicator_accuracy(self, days: int = 30, threshold: float = 50.0) -> dict:
        """지표별 극단값 적중률. 각 지표가 ±threshold 이상일 때 시장 방향 적중률."""
        records = self.store.get_recent(limit=days)
        evaluated = [r for r in records if r["hit_1d"] is not None and r["indicator_scores"]]

        result: dict[str, dict[str, Any]] = {}
        for record in evaluated:
            try:
                indicators = (
                    json.loads(record["indicator_scores"])
                    if isinstance(record["indicator_scores"], str)
                    else record["indicator_scores"]
                )
            except (json.JSONDecodeError, TypeError):
                continue

            hit = record["hit_1d"]
            for key, value in indicators.items():
                if value is None:
                    continue
                if abs(value) >= threshold:
                    if key not in result:
                        result[key] = {"hits": 0, "total": 0}
                    result[key]["total"] += 1
                    result[key]["hits"] += hit

        # Calculate rates
        for key in result:
            total = result[key]["total"]
            result[key]["accuracy"] = round(result[key]["hits"] / total, 2) if total > 0 else 0.0

        return result

    def get_correlation(self, days: int = 30) -> float | None:
        """시그널 강도 vs 1일 수익률 Pearson 상관계수."""
        records = self.store.get_recent(limit=days)
        pairs = [
            (r["score"], r["return_1d"])
            for r in records
            if r["score"] is not None and r["return_1d"] is not None
        ]

        if len(pairs) < 5:  # minimum for meaningful correlation
            return None

        scores = np.array([p[0] for p in pairs])
        returns = np.array([p[1] for p in pairs])

        corr_matrix = np.corrcoef(scores, returns)
        corr = float(corr_matrix[0, 1])
        return round(corr, 3) if not np.isnan(corr) else None
