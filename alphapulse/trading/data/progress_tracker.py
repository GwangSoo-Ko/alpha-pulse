"""데이터 수집 진행률 추적기.

ETA 계산, 진행률 바, 단계별 요약, 중단 후 재개(checkpoint)를 지원한다.
"""

import sys
import time
from pathlib import Path


def _format_time(seconds: float) -> str:
    """초를 읽기 쉬운 형태로 변환한다."""
    if seconds < 60:
        return f"{seconds:.0f}초"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}분 {seconds % 60:.0f}초"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}시간 {m}분"


def _progress_bar(pct: float, width: int = 25) -> str:
    """퍼센트를 프로그레스 바로 변환한다."""
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


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
        self._last_print_time: float = 0

    def start(self) -> None:
        """타이머를 시작한다."""
        self._start_time = time.time()
        self._last_print_time = 0
        self._completed = 0
        self._skipped = 0
        self._print_header()

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
        return codes[idx + 1:]

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
        """진행률을 stderr에 출력한다. 0.5초 간격으로 갱신."""
        now = time.time()
        if now - self._last_print_time < 0.5 and self._completed < self.total:
            return
        self._last_print_time = now

        s = self.summary()
        pct = (s["completed"] / s["total"] * 100) if s["total"] > 0 else 0
        bar = _progress_bar(pct)
        elapsed = _format_time(s["elapsed_seconds"])
        eta = _format_time(s["eta_seconds"])
        rate = s["rate_per_second"]
        ok = s["completed"] - s["skipped"]
        skip = s["skipped"]

        line = (
            f"\r  {bar} {pct:5.1f}%  "
            f"{s['completed']:>5}/{s['total']}  "
            f"({ok} ok, {skip} skip)  "
            f"{current_code:<8}  "
            f"{elapsed} / ~{eta}  "
            f"({rate:.1f}/s)"
        )
        # 줄 끝 공백으로 이전 긴 텍스트 덮기
        sys.stderr.write(f"{line:<100}")
        sys.stderr.flush()

    def print_summary(self) -> None:
        """단계 완료 요약을 출력한다."""
        s = self.summary()
        elapsed = _format_time(s["elapsed_seconds"])
        ok = s["completed"] - s["skipped"]
        sys.stderr.write("\n")
        sys.stderr.write(
            f"  -> {self.label} 완료: "
            f"{ok}건 성공, {s['skipped']}건 스킵 ({elapsed})\n"
        )
        sys.stderr.flush()

    def _print_header(self) -> None:
        """단계 시작 헤더를 출력한다."""
        resumed = self.total - (self._completed or self.total)
        msg = f"\n  {self.label} ({self.total}건)"
        if resumed > 0:
            msg += f" [재개: {resumed}건 완료됨]"
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

    def _checkpoint_path(self) -> Path:
        import re
        safe_label = re.sub(r"[^a-z0-9_]", "_", self.label.lower()) or "default"
        return self.checkpoint_dir / f".collection_checkpoint_{safe_label}"
