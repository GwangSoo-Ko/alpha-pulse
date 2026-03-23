import logging
import re
from datetime import datetime
from pathlib import Path

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()


class ReportWriter:
    def __init__(self, reports_dir: str = _cfg.REPORTS_DIR):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        title: str,
        url: str,
        published: str,
        category: str,
        analysis: str,
        original_content: str,
        source_tag: str = "",
    ) -> Path:
        filename = self._generate_filename(category or "미분류", title)
        filepath = self.reports_dir / filename
        report = self._build_report(title, url, published, category, analysis, original_content, source_tag)
        filepath.write_text(report, encoding="utf-8")
        logger.info(f"보고서 저장: {filepath}")
        return filepath

    def _generate_filename(self, category: str, title: str) -> str:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_cat = re.sub(r'[\\/:*?"<>|\s]+', '_', category)
        safe_title = re.sub(r'[\\/:*?"<>|\s]+', '_', title)[:50].rstrip('_')
        return f"{now}_{safe_cat}_{safe_title}.md"

    def _build_report(
        self,
        title: str,
        url: str,
        published: str,
        category: str,
        analysis: str,
        original_content: str,
        source_tag: str = "",
    ) -> str:
        analyzed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cat_display = category or "미분류"
        source_tag_line = f'\nsource_tag: "{source_tag}"' if source_tag else ""
        title_line = f"# {source_tag} {title}" if source_tag else f"# {title}"
        return f"""---
title: "{title}"
source: "{url}"
published: "{published}"
analyzed_at: "{analyzed_at}"
category: "{cat_display}"{source_tag_line}
---

{title_line}
> **원문 링크:** {url}
> **발행일:** {published} | **카테고리:** {cat_display}
> **분석일:** {analyzed_at}

---

{analysis}

---

<details>
<summary>원문 전문 (접기/펼치기)</summary>

{original_content}

</details>
"""
