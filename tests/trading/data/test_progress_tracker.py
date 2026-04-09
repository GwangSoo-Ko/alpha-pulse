"""진행률 추적기 테스트."""
from alphapulse.trading.data.progress_tracker import ProgressTracker


class TestProgressTracker:
    def test_advance(self, tmp_path):
        pt = ProgressTracker(total=10, label="test", checkpoint_dir=tmp_path)
        pt.start()
        pt.advance()
        pt.advance()
        summary = pt.summary()
        assert summary["completed"] == 2
        assert summary["total"] == 10

    def test_checkpoint_and_resume(self, tmp_path):
        pt = ProgressTracker(total=5, label="test", checkpoint_dir=tmp_path)
        pt.checkpoint("005930")
        pt.checkpoint("000660")

        codes = ["005930", "000660", "035720", "051910"]
        remaining = pt.get_resume_point(codes)
        assert remaining == ["035720", "051910"]

    def test_no_checkpoint_returns_all(self, tmp_path):
        pt = ProgressTracker(total=3, label="test", checkpoint_dir=tmp_path)
        codes = ["005930", "000660", "035720"]
        remaining = pt.get_resume_point(codes)
        assert remaining == codes

    def test_cleanup(self, tmp_path):
        pt = ProgressTracker(total=3, label="test", checkpoint_dir=tmp_path)
        pt.checkpoint("005930")
        cp_file = tmp_path / ".collection_checkpoint_test"
        assert cp_file.exists()
        pt.cleanup()
        assert not cp_file.exists()

    def test_skipped_count(self, tmp_path):
        pt = ProgressTracker(total=5, label="test", checkpoint_dir=tmp_path)
        pt.start()
        pt.advance(skipped=True)
        pt.advance()
        assert pt.summary()["skipped"] == 1
