"""ContentReader mtime-based scan cache 테스트."""

from pathlib import Path

from alphapulse.webapp.store.readers.content import ContentReader


def _write_report(dir_path: Path, name: str, title: str = "T") -> None:
    (dir_path / name).write_text(
        f"---\ntitle: {title}\ncategory: 테스트\npublished: 2026-04-01\nanalyzed_at: 2026-04-02T10:00\n---\n\n본문\n",
        encoding="utf-8",
    )


def test_scan_cache_hit_uses_no_file_io(tmp_path, monkeypatch):
    _write_report(tmp_path, "a.md")
    reader = ContentReader(tmp_path)

    # 첫 호출: 실제 스캔
    first = reader._scan()
    assert len(first) == 1

    # iterdir 을 모킹해서 두 번째 호출이 디스크 접근 없어야 함
    call_count = {"n": 0}

    real_iterdir = Path.iterdir

    def counting_iterdir(self):
        call_count["n"] += 1
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", counting_iterdir)

    second = reader._scan()
    assert second == first
    assert call_count["n"] == 0  # 캐시 히트: iterdir 호출 없음


def test_scan_cache_invalidates_on_new_file(tmp_path):
    _write_report(tmp_path, "a.md")
    reader = ContentReader(tmp_path)
    first = reader._scan()
    assert len(first) == 1

    # 새 파일 추가 → 디렉터리 mtime 변경
    import time
    time.sleep(0.01)  # fs mtime 해상도 우회
    _write_report(tmp_path, "b.md")

    second = reader._scan()
    assert len(second) == 2


def test_scan_returns_empty_for_missing_dir(tmp_path):
    missing = tmp_path / "nonexistent"
    reader = ContentReader(missing)
    assert reader._scan() == []
    # 두 번째 호출도 안전
    assert reader._scan() == []
