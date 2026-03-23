import logging

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()


class CategoryFilter:
    def __init__(
        self,
        target_categories: list[str] = _cfg.TARGET_CATEGORIES,
        skip_unknown: bool = _cfg.SKIP_UNKNOWN_CATEGORY,
    ):
        self.target_categories = target_categories
        self.skip_unknown = skip_unknown

    def is_target_category(self, category: str | None) -> bool:
        if not category:
            return False
        return any(target in category for target in self.target_categories)

    def filter_posts(self, posts: list[dict]) -> tuple[list[dict], list[dict]]:
        target = []
        skipped = []
        for post in posts:
            cat = post.get("category")
            if self.is_target_category(cat):
                logger.info(f'[TARGET] "{post["title"]}" - 카테고리: {cat}')
                target.append(post)
            else:
                reason = f"카테고리: {cat}" if cat else "카테고리 불명"
                logger.info(f'[SKIP] "{post["title"]}" - {reason} (대상 아님)')
                skipped.append(post)
        return target, skipped
