
import pytest

from alphapulse.content.reporter import ReportWriter


@pytest.fixture
def writer(tmp_path):
    return ReportWriter(reports_dir=str(tmp_path))


def test_generate_filename(writer):
    fname = writer._generate_filename("경제", "트럼프 관세 정책의 영향 분석 보고서 제목이 매우 길 수 있습니다")
    assert fname.startswith("20")
    assert "경제" in fname
    assert fname.endswith(".md")
    # title part should be truncated to 50 chars
    assert len(fname) <= 120  # reasonable length


def test_generate_filename_special_chars(writer):
    fname = writer._generate_filename("주식", '제목에 "특수문자" /포함\\된 경우')
    assert '"' not in fname
    assert '/' not in fname
    assert '\\' not in fname


def test_build_report(writer):
    report = writer._build_report(
        title="테스트 글",
        url="https://blog.naver.com/ranto28/123",
        published="2026-03-16",
        category="경제",
        analysis="## 핵심 요약\n테스트 분석",
        original_content="원본 텍스트",
    )
    assert "테스트 글" in report
    assert "원문 링크" in report
    assert "경제" in report
    assert "원본 텍스트" in report
    assert "핵심 요약" in report


def test_build_report_no_category(writer):
    report = writer._build_report(
        title="제목", url="https://example.com",
        published="2026-03-16", category=None,
        analysis="분석", original_content="원본",
    )
    assert "미분류" in report


def test_save_report(writer):
    path = writer.save(
        title="테스트",
        url="https://example.com",
        published="2026-03-16",
        category="경제",
        analysis="분석 결과",
        original_content="원본",
    )
    assert path.exists()
    content = path.read_text()
    assert "테스트" in content
    assert "경제" in content


def test_build_report_with_source_tag(writer):
    report = writer._build_report(
        title="채널 글",
        url="https://t.me/example/123",
        published="2026-03-16",
        category="채널",
        analysis="## 핵심 요약\n채널 분석",
        original_content="원본 텍스트",
        source_tag="[채널분석]",
    )
    assert "# [채널분석] 채널 글" in report
    assert 'source_tag: "[채널분석]"' in report


def test_build_report_without_source_tag(writer):
    report = writer._build_report(
        title="일반 글",
        url="https://blog.naver.com/test/456",
        published="2026-03-16",
        category="경제",
        analysis="분석 내용",
        original_content="원본",
    )
    assert "# 일반 글" in report
    assert "source_tag" not in report


def test_save_with_source_tag(writer):
    path = writer.save(
        title="채널 테스트",
        url="https://t.me/example/789",
        published="2026-03-16",
        category="채널",
        analysis="분석 결과",
        original_content="원본",
        source_tag="[채널분석]",
    )
    assert path.exists()
    content = path.read_text()
    assert "[채널분석]" in content
    assert "# [채널분석] 채널 테스트" in content
    assert 'source_tag: "[채널분석]"' in content


def test_reports_dir_created(tmp_path):
    new_dir = tmp_path / "sub" / "reports"
    ReportWriter(reports_dir=str(new_dir))
    assert new_dir.exists()
