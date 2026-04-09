"""백테스트 리포트 — 터미널 + HTML 출력.

성과 지표, 자산 곡선, 거래 요약을 포맷팅한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphapulse.trading.backtest.engine import BacktestResult


class BacktestReport:
    """백테스트 결과를 터미널 텍스트 또는 HTML로 포맷팅한다."""

    def to_terminal(self, result: BacktestResult) -> str:
        """터미널용 텍스트 리포트를 생성한다.

        Args:
            result: 백테스트 결과.

        Returns:
            포맷된 텍스트 문자열.
        """
        m = result.metrics
        c = result.config
        lines = [
            "=" * 60,
            "  백테스트 결과 리포트",
            "=" * 60,
            "",
            f"  기간: {c.start_date} ~ {c.end_date}",
            f"  초기 자본: {c.initial_capital:,.0f}원",
            f"  최종 자산: {result.snapshots[-1].total_value:,.0f}원" if result.snapshots else "",
            f"  벤치마크: {c.benchmark}",
            "",
            "--- 수익률 ---",
            f"  총 수익률:     {m.get('total_return', 0):.4f}%",
            f"  CAGR:          {m.get('cagr', 0):.4f}%",
            f"  변동성:        {m.get('volatility', 0):.4f}%",
            "",
            "--- 리스크 ---",
            f"  최대 낙폭:     {m.get('max_drawdown', 0):.4f}%",
            f"  MDD 지속:      {m.get('max_drawdown_duration', 0)}일",
            f"  하방 변동성:   {m.get('downside_deviation', 0):.4f}%",
            "",
            "--- 리스크 조정 ---",
            f"  샤프 비율:     {m.get('sharpe_ratio', 0):.4f}",
            f"  소르티노:      {m.get('sortino_ratio', 0):.4f}",
            f"  칼마 비율:     {m.get('calmar_ratio', 0):.4f}",
            "",
            "--- 거래 ---",
            f"  총 거래:       {m.get('total_trades', 0)}회",
            f"  승률:          {m.get('win_rate', 0):.1f}%",
            f"  이익 팩터:     {m.get('profit_factor', 0):.4f}",
            f"  평균 수익:     {m.get('avg_win', 0):,.2f}원",
            f"  평균 손실:     {m.get('avg_loss', 0):,.2f}원",
            f"  회전율:        {m.get('turnover', 0):.4f}",
            "",
            f"--- 벤치마크 ({c.benchmark}) ---",
            f"  벤치마크 수익: {m.get('benchmark_return', 0):.4f}%",
            f"  초과 수익:     {m.get('excess_return', 0):.4f}%",
            f"  베타:          {m.get('beta', 0):.4f}",
            f"  알파:          {m.get('alpha', 0):.4f}%",
            f"  정보 비율:     {m.get('information_ratio', 0):.4f}",
            f"  추적 오차:     {m.get('tracking_error', 0):.4f}%",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    def to_html(self, result: BacktestResult) -> str:
        """HTML 리포트를 생성한다.

        Args:
            result: 백테스트 결과.

        Returns:
            HTML 문자열.
        """
        m = result.metrics
        c = result.config

        # 자산 곡선 데이터
        dates_js = ", ".join(f'"{s.date}"' for s in result.snapshots)
        values_js = ", ".join(str(int(s.total_value)) for s in result.snapshots)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <title>백테스트 리포트 | {c.start_date} ~ {c.end_date}</title>
    <style>
        body {{ font-family: 'Pretendard', -apple-system, sans-serif; margin: 40px; background: #f8f9fa; }}
        h1 {{ color: #1a1a2e; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }}
        .metric-card {{ background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .metric-label {{ font-size: 0.85em; color: #666; }}
        .metric-value {{ font-size: 1.4em; font-weight: 700; color: #1a1a2e; }}
        .metric-value.positive {{ color: #e74c3c; }}
        .metric-value.negative {{ color: #3498db; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 10px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #1a1a2e; color: white; }}
        .equity-chart {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>백테스트 결과 리포트</h1>
    <p>기간: {c.start_date} ~ {c.end_date} | 초기 자본: {c.initial_capital:,.0f}원 | 벤치마크: {c.benchmark}</p>

    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">총 수익률</div>
            <div class="metric-value {'positive' if m.get('total_return', 0) >= 0 else 'negative'}">{m.get('total_return', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">CAGR</div>
            <div class="metric-value">{m.get('cagr', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">샤프 비율</div>
            <div class="metric-value">{m.get('sharpe_ratio', 0):.4f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">소르티노 비율</div>
            <div class="metric-value">{m.get('sortino_ratio', 0):.4f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">최대 낙폭</div>
            <div class="metric-value negative">{m.get('max_drawdown', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">승률</div>
            <div class="metric-value">{m.get('win_rate', 0):.1f}%</div>
        </div>
    </div>

    <div class="section">
        <h2>자산 곡선</h2>
        <div class="equity-chart">
            <canvas id="equityChart" width="800" height="300"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>상세 지표</h2>
        <table>
            <tr><th>카테고리</th><th>지표</th><th>값</th></tr>
            <tr><td>수익률</td><td>총 수익률</td><td>{m.get('total_return', 0):.4f}%</td></tr>
            <tr><td>수익률</td><td>CAGR</td><td>{m.get('cagr', 0):.4f}%</td></tr>
            <tr><td>수익률</td><td>변동성</td><td>{m.get('volatility', 0):.4f}%</td></tr>
            <tr><td>리스크</td><td>최대 낙폭</td><td>{m.get('max_drawdown', 0):.4f}%</td></tr>
            <tr><td>리스크</td><td>MDD 지속</td><td>{m.get('max_drawdown_duration', 0)}일</td></tr>
            <tr><td>리스크</td><td>하방 변동성</td><td>{m.get('downside_deviation', 0):.4f}%</td></tr>
            <tr><td>리스크 조정</td><td>샤프 비율</td><td>{m.get('sharpe_ratio', 0):.4f}</td></tr>
            <tr><td>리스크 조정</td><td>소르티노 비율</td><td>{m.get('sortino_ratio', 0):.4f}</td></tr>
            <tr><td>리스크 조정</td><td>칼마 비율</td><td>{m.get('calmar_ratio', 0):.4f}</td></tr>
            <tr><td>거래</td><td>총 거래</td><td>{m.get('total_trades', 0)}회</td></tr>
            <tr><td>거래</td><td>승률</td><td>{m.get('win_rate', 0):.1f}%</td></tr>
            <tr><td>거래</td><td>이익 팩터</td><td>{m.get('profit_factor', 0):.4f}</td></tr>
            <tr><td>거래</td><td>회전율</td><td>{m.get('turnover', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>벤치마크 수익</td><td>{m.get('benchmark_return', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>초과 수익</td><td>{m.get('excess_return', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>베타</td><td>{m.get('beta', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>알파</td><td>{m.get('alpha', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>정보 비율</td><td>{m.get('information_ratio', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>추적 오차</td><td>{m.get('tracking_error', 0):.4f}%</td></tr>
        </table>
    </div>

    <script>
        // 자산 곡선 — 간단한 Canvas 차트
        const dates = [{dates_js}];
        const values = [{values_js}];
        const canvas = document.getElementById('equityChart');
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        const padding = 60;
        const minV = Math.min(...values) * 0.995;
        const maxV = Math.max(...values) * 1.005;
        const xStep = (w - padding * 2) / (values.length - 1 || 1);

        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 2;
        ctx.beginPath();
        values.forEach((v, i) => {{
            const x = padding + i * xStep;
            const y = h - padding - ((v - minV) / (maxV - minV)) * (h - padding * 2);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }});
        ctx.stroke();

        // 축 레이블
        ctx.fillStyle = '#666';
        ctx.font = '11px sans-serif';
        ctx.fillText(dates[0], padding, h - 10);
        ctx.fillText(dates[dates.length - 1], w - padding - 60, h - 10);
        ctx.fillText(minV.toLocaleString(), 0, h - padding);
        ctx.fillText(maxV.toLocaleString(), 0, padding + 10);
    </script>
</body>
</html>"""
        return html

    def save_html(self, result: BacktestResult, path: str) -> None:
        """HTML 리포트를 파일로 저장한다.

        Args:
            result: 백테스트 결과.
            path: 저장 경로.
        """
        html = self.to_html(result)
        Path(path).write_text(html, encoding="utf-8")
