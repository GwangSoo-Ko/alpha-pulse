"""ContentReader — ./reports/*.md 디렉토리 스캔 + YAML frontmatter 파싱.

Read-only. 실제 리포트 쓰기는 `alphapulse.content.reporter.ReportWriter` 가 담당.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, TypedDict

import yaml

logger = logging.getLogger(__name__)


class ReportMeta(TypedDict):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str


class ReportFull(ReportMeta):
    body: str


class ListResult(TypedDict):
    items: list[ReportMeta]
    total: int
    page: int
    size: int
    categories: list[str]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """마크다운 텍스트에서 frontmatter + body 분리.

    frontmatter 가 없거나 파싱 실패 시 (빈 dict, 원본 텍스트).
    """
    if not text.startswith("---"):
        return {}, text
    # 첫 줄 이후 --- 까지 찾기
    lines = text.split("\n")
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx < 0:
        return {}, text
    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    try:
        meta = yaml.safe_load(yaml_text) or {}
        if not isinstance(meta, dict):
            logger.warning("frontmatter 가 dict 가 아님: %r", meta)
            return {}, body
        return meta, body
    except yaml.YAMLError as e:
        logger.warning("YAML 파싱 실패: %s", e)
        return {}, body


def _meta_from_file(path: Path) -> ReportMeta:
    """파일에서 frontmatter 파싱. 실패 시 fallback."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        logger.warning("파일 읽기 실패 %s: %s", path, e)
        text = ""
    fm, _body = _parse_frontmatter(text)
    return {
        "filename": path.name,
        "title": str(fm.get("title") or path.stem),
        "category": str(fm.get("category") or "미분류"),
        "published": str(fm.get("published") or ""),
        "analyzed_at": str(fm.get("analyzed_at") or ""),
        "source": str(fm.get("source") or ""),
        "source_tag": str(fm.get("source_tag") or ""),
    }


def _date_in_range(
    published: str, date_from: str | None, date_to: str | None,
) -> bool:
    """published(YYYY-MM-DD 또는 YYYYMMDD) 가 date_from~date_to 범위에 있는지."""
    if not date_from and not date_to:
        return True
    if not published:
        return False
    normalized = published.replace("-", "").replace(".", "")[:8]
    if not normalized.isdigit() or len(normalized) != 8:
        return False
    if date_from and normalized < date_from:
        return False
    if date_to and normalized > date_to:
        return False
    return True


class ContentReader:
    """./reports/*.md 읽기 전용 리더."""

    def __init__(self, reports_dir: Path | str) -> None:
        self.reports_dir = Path(reports_dir)

    def _scan(self) -> list[ReportMeta]:
        if not self.reports_dir.is_dir():
            return []
        metas: list[ReportMeta] = []
        for entry in self.reports_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".md":
                continue
            if entry.name.startswith("."):
                continue
            metas.append(_meta_from_file(entry))
        return metas

    def list_reports(
        self,
        *,
        categories: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        query: str | None = None,
        sort: Literal["newest", "oldest"] = "newest",
        page: int = 1,
        size: int = 20,
    ) -> ListResult:
        all_metas = self._scan()
        # 필터
        filtered = [
            m for m in all_metas
            if (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
            and (not query or query.lower() in m["title"].lower())
        ]
        # 정렬 (analyzed_at 기준)
        reverse = sort == "newest"
        filtered.sort(key=lambda m: m["analyzed_at"], reverse=reverse)
        # 페이지네이션
        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        items = filtered[start:end]
        # 전체 파일 기준 distinct 카테고리
        categories_all = sorted({m["category"] for m in all_metas})
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "categories": categories_all,
        }

    def get_report(self, filename: str) -> ReportFull | None:
        path = self.reports_dir / filename
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            logger.warning("파일 읽기 실패 %s: %s", path, e)
            return None
        fm, body = _parse_frontmatter(text)
        return {
            "filename": path.name,
            "title": str(fm.get("title") or path.stem),
            "category": str(fm.get("category") or "미분류"),
            "published": str(fm.get("published") or ""),
            "analyzed_at": str(fm.get("analyzed_at") or ""),
            "source": str(fm.get("source") or ""),
            "source_tag": str(fm.get("source_tag") or ""),
            "body": body,
        }

    def distinct_categories(self) -> list[str]:
        return sorted({m["category"] for m in self._scan()})
