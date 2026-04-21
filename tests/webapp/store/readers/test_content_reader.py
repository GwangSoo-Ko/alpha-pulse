"""ContentReader — 디렉토리 스캔 + frontmatter 파싱 + 필터."""
from pathlib import Path

import pytest

from alphapulse.webapp.store.readers.content import ContentReader


def _write_report(
    dirpath: Path,
    filename: str,
    *,
    title: str = "테스트",
    category: str = "경제",
    published: str = "2026-04-20",
    analyzed_at: str = "2026-04-20 15:30:00",
    source: str = "https://example.com",
    source_tag: str = "",
    body: str = "본문",
) -> Path:
    tag_line = f'source_tag: "{source_tag}"\n' if source_tag else ""
    content = (
        f'---\n'
        f'title: "{title}"\n'
        f'source: "{source}"\n'
        f'published: "{published}"\n'
        f'analyzed_at: "{analyzed_at}"\n'
        f'category: "{category}"\n'
        f'{tag_line}'
        f'---\n\n'
        f'{body}\n'
    )
    path = dirpath / filename
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


def test_list_reports_empty(reports_dir):
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["items"] == []
    assert result["total"] == 0
    assert result["page"] == 1
    assert result["size"] == 20


def test_list_reports_parses_frontmatter(reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", category="경제")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["filename"] == "a.md"
    assert item["title"] == "글 A"
    assert item["category"] == "경제"
    assert item["published"] == "2026-04-20"
    assert item["source"] == "https://example.com"


def test_list_reports_ignores_non_md_files(reports_dir):
    _write_report(reports_dir, "a.md")
    (reports_dir / "b.txt").write_text("not md")
    (reports_dir / ".hidden.md").write_text("hidden")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    # .md 이면서 숨김이 아닌 것만
    assert result["total"] == 1


def test_list_reports_filters_by_category(reports_dir):
    _write_report(reports_dir, "a.md", title="A", category="경제")
    _write_report(reports_dir, "b.md", title="B", category="주식")
    _write_report(reports_dir, "c.md", title="C", category="사회")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(categories=["경제", "주식"])
    titles = {i["title"] for i in result["items"]}
    assert titles == {"A", "B"}


def test_list_reports_filters_by_date_range(reports_dir):
    _write_report(reports_dir, "a.md", title="A", published="2026-03-10")
    _write_report(reports_dir, "b.md", title="B", published="2026-04-15")
    _write_report(reports_dir, "c.md", title="C", published="2026-05-01")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(date_from="20260401", date_to="20260430")
    titles = {i["title"] for i in result["items"]}
    assert titles == {"B"}


def test_list_reports_filters_by_query_case_insensitive(reports_dir):
    _write_report(reports_dir, "a.md", title="버핏의 투자 철학")
    _write_report(reports_dir, "b.md", title="테슬라 주가 분석")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(query="버핏")
    assert result["total"] == 1
    assert result["items"][0]["title"] == "버핏의 투자 철학"


def test_list_reports_sort_newest_first_by_analyzed_at(reports_dir):
    _write_report(reports_dir, "a.md", title="A", analyzed_at="2026-04-20 10:00:00")
    _write_report(reports_dir, "b.md", title="B", analyzed_at="2026-04-21 10:00:00")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(sort="newest")
    assert [i["title"] for i in result["items"]] == ["B", "A"]


def test_list_reports_sort_oldest_first(reports_dir):
    _write_report(reports_dir, "a.md", title="A", analyzed_at="2026-04-20 10:00:00")
    _write_report(reports_dir, "b.md", title="B", analyzed_at="2026-04-21 10:00:00")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(sort="oldest")
    assert [i["title"] for i in result["items"]] == ["A", "B"]


def test_list_reports_pagination(reports_dir):
    for i in range(5):
        _write_report(
            reports_dir, f"r{i:02d}.md", title=f"R{i}",
            analyzed_at=f"2026-04-{20-i:02d} 10:00:00",
        )
    reader = ContentReader(reports_dir=reports_dir)
    page1 = reader.list_reports(page=1, size=2)
    page2 = reader.list_reports(page=2, size=2)
    page3 = reader.list_reports(page=3, size=2)
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 1


def test_list_reports_fallback_for_missing_frontmatter(reports_dir):
    """frontmatter 없는 파일도 skip 하지 않고 파일명을 title 로 사용."""
    (reports_dir / "no_fm.md").write_text("# 그냥 마크다운\n\n본문", encoding="utf-8")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["filename"] == "no_fm.md"
    assert item["title"] == "no_fm"   # stem
    assert item["category"] == "미분류"


def test_list_reports_fallback_for_malformed_yaml(reports_dir):
    """깨진 YAML 도 skip 하지 않고 fallback 사용."""
    (reports_dir / "bad.md").write_text(
        "---\ntitle: 짝 따옴표 없음\n bad: : yaml\n---\n본문",
        encoding="utf-8",
    )
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1


def test_get_report_returns_body(reports_dir):
    _write_report(reports_dir, "a.md", title="글", body="이것은 본문이다")
    reader = ContentReader(reports_dir=reports_dir)
    detail = reader.get_report("a.md")
    assert detail is not None
    assert detail["title"] == "글"
    assert "이것은 본문이다" in detail["body"]
    # frontmatter 는 body 에 포함되지 않음
    assert "---" not in detail["body"][:10]


def test_get_report_returns_none_when_missing(reports_dir):
    reader = ContentReader(reports_dir=reports_dir)
    assert reader.get_report("missing.md") is None


def test_distinct_categories(reports_dir):
    _write_report(reports_dir, "a.md", category="경제")
    _write_report(reports_dir, "b.md", category="주식")
    _write_report(reports_dir, "c.md", category="경제")
    reader = ContentReader(reports_dir=reports_dir)
    cats = reader.distinct_categories()
    assert sorted(cats) == ["경제", "주식"]
