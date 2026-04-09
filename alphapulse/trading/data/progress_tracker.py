"""데이터 수집 진행률 추적기.

ETA 계산, 진행률 표시, 중단 후 재개(checkpoint)를 지원한다.
"""

import sys
import time
from pathlib import Path


class ProgressTracker:
    """진행률 추적기.

    Attributes:
        total: 전체 작업 수.
        label: 작업 라벨 (예: "KOSPI OHLCV").
        checkpoint_dir: 체크포인트 파일 디렉토리.
    """

    def __init__(
        self,
        total: int,
        label: str = "",
        checkpoint_dir: str | Path = ".",
    ) -> None:
        self.total = total
        self.label = label
        self.checkpoint_dir = Path(checkpoint_dir)
        self._completed = 0
        self._skipped = 0
        self._start_time: float = 0

    def start(self) -> None:
        """타이머를 시작한다."""
        self._start_time = time.time()
        self._completed = 0
        self._skipped = 0

    def advance(self, n: int = 1, skipped: bool = False) -> None:
        """진행률을 갱신한다."""
        self._completed += n
        if skipped:
            self._skipped += n

    def checkpoint(self, completed_code: str) -> None:
        """마지막 완료 종목을 체크포인트에 저장한다."""
        cp_path = self._checkpoint_path()
        tmp_path = cp_path.with_suffix(".tmp")
        tmp_path.write_text(completed_code)
        tmp_path.rename(cp_path)

    def get_resume_point(self, codes: list[str]) -> list[str]:
        """체크포인트 이후 남은 종목 목록을 반환한다."""
        cp_path = self._checkpoint_path()
        if not cp_path.exists():
            return codes
        last_code = cp_path.read_text().strip()
        if last_code not in codes:
            return codes
        idx = codes.index(last_code)
        return codes[idx + 1 :]

    def cleanup(self) -> None:
        """체크포인트 파일을 삭제한다."""
        cp_path = self._checkpoint_path()
        if cp_path.exists():
            cp_path.unlink()

    def summary(self) -> dict:
        """현재 진행 상황 요약."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        rate = self._completed / elapsed if elapsed > 0 else 0
        remaining = self.total - self._completed
        eta = remaining / rate if rate > 0 else 0
        return {
            "completed": self._completed,
            "total": self.total,
            "skipped": self._skipped,
            "elapsed_seconds": elapsed,
            "rate_per_second": rate,
            "eta_seconds": eta,
        }

    def print_progress(self, current_code: str = "") -> None:
        """진행률을 stderr에 출력한다."""
        s = self.summary()
        pct = (s["completed"] / s["total"] * 100) if s["total"] > 0 else 0
        eta_min = s["eta_seconds"] / 60
        msg = (
            f"\r[{s['completed']}/{s['total']}] {pct:.1f}% "
            f"| {self.label} {current_code} | ETA {eta_min:.0f}m"
        )
        sys.stderr.write(msg)
        sys.stderr.flush()

    def _checkpoint_path(self) -> Path:
        safe_label = self.label.replace(" ", "_").lower() or "default"
        return self.checkpoint_dir / f".collection_checkpoint_{safe_label}"
