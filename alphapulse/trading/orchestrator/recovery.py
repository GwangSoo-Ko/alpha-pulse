"""RecoveryManager — 장애 복구 + DB/브로커 대사.

시스템 재시작 시 마지막 스냅샷과 브로커 실제 잔고를 비교한다.
불일치 발견 시 경고만 하고 자동 수정은 하지 않는다 (안전 우선).
"""

import logging

from alphapulse.trading.core.models import Position

logger = logging.getLogger(__name__)


class RecoveryManager:
    """장애 복구 관리자.

    재시작 시 DB 포트폴리오와 브로커 실제 잔고를 대사(reconcile)한다.
    불일치 발견 시 경고 메시지를 반환하되, 절대 자동 수정하지 않는다.

    Attributes:
        broker: Broker Protocol 구현체.
        store: 포트폴리오 저장소 (get_latest_snapshot 메서드).
        alert: 알림 인스턴스 (경고 전송용).
    """

    def __init__(self, broker, store, alert) -> None:
        """RecoveryManager를 초기화한다.

        Args:
            broker: Broker Protocol 구현체.
            store: 포트폴리오 저장소.
            alert: 알림 인스턴스 (경고 전송용).
        """
        self.broker = broker
        self.store = store
        self.alert = alert

    def reconcile(self) -> list[str]:
        """DB 포지션과 브로커 실제 잔고를 대사한다.

        종목코드 + 수량 기준으로 비교한다.
        비중(weight)과 전략 ID는 무시한다 (브로커에 해당 정보 없음).

        Returns:
            불일치 경고 메시지 리스트. 일치하면 빈 리스트.
        """
        warnings: list[str] = []

        # DB 스냅샷 로드
        snapshot = self.store.get_latest_snapshot()
        if snapshot is None:
            logger.info("DB 스냅샷 없음 — 신규 시작으로 판단")
            return warnings

        db_positions = snapshot.positions
        broker_positions = self.broker.get_positions()

        # 종목코드 -> Position 매핑
        db_map: dict[str, Position] = {p.stock.code: p for p in db_positions}
        broker_map: dict[str, Position] = {p.stock.code: p for p in broker_positions}

        # DB에 있지만 브로커에 없는 종목
        for code in db_map:
            if code not in broker_map:
                warnings.append(
                    f"DB에만 존재: {code} ({db_map[code].stock.name}) "
                    f"DB수량={db_map[code].quantity}"
                )

        # 브로커에 있지만 DB에 없는 종목
        for code in broker_map:
            if code not in db_map:
                warnings.append(
                    f"브로커에만 존재: {code} ({broker_map[code].stock.name}) "
                    f"브로커수량={broker_map[code].quantity}"
                )

        # 양쪽 모두에 있지만 수량이 다른 종목
        for code in db_map:
            if code in broker_map:
                db_qty = db_map[code].quantity
                broker_qty = broker_map[code].quantity
                if db_qty != broker_qty:
                    warnings.append(
                        f"수량 불일치: {code} ({db_map[code].stock.name}) "
                        f"DB={db_qty} vs 브로커={broker_qty}"
                    )

        if warnings:
            logger.warning("대사 불일치 발견: %d건", len(warnings))
            for w in warnings:
                logger.warning("  %s", w)
        else:
            logger.info("대사 완료: 불일치 없음")

        return warnings

    def on_crash_recovery(self) -> dict:
        """시스템 재시작 시 복구를 수행한다.

        1. 마지막 스냅샷 로드
        2. 브로커 실제 잔고 조회
        3. 대사 수행
        4. 불일치 발견 시 경고

        자동 수정은 하지 않는다. 사람이 확인 후 수동으로 처리해야 한다.

        Returns:
            {"recovered": bool, "warnings": list[str], "snapshot_date": str | None}.
        """
        logger.info("장애 복구 시작")

        snapshot = self.store.get_latest_snapshot()
        snapshot_date = snapshot.date if snapshot else None

        if snapshot is None:
            logger.info("스냅샷 없음 — 신규 시작")
            return {
                "recovered": True,
                "warnings": [],
                "snapshot_date": None,
            }

        logger.info("마지막 스냅샷: %s (자산: %.0f원)",
                     snapshot.date, snapshot.total_value)

        warnings = self.reconcile()

        return {
            "recovered": True,
            "warnings": warnings,
            "snapshot_date": snapshot_date,
        }
