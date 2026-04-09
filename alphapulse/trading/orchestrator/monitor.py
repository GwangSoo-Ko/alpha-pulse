"""SystemMonitor — 시스템 헬스체크.

브로커, 데이터 소스, 저장소, 리스크 매니저 등 서브시스템의
상태를 점검하고 결과를 반환한다.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemMonitor:
    """시스템 헬스체크 모니터.

    등록된 컴포넌트의 연결 상태를 점검한다.
    브로커는 get_balance(), 나머지는 ping() 호출로 확인한다.

    Attributes:
        components: {이름: 인스턴스} 딕셔너리.
    """

    def __init__(self, components: dict) -> None:
        """SystemMonitor를 초기화한다.

        Args:
            components: 서브시스템 딕셔너리. 키는 이름, 값은 인스턴스.
        """
        self.components = components

    def component_names(self) -> list[str]:
        """등록된 컴포넌트 이름 목록을 반환한다.

        Returns:
            컴포넌트 이름 리스트.
        """
        return list(self.components.keys())

    def check_health(self) -> dict:
        """전체 시스템 헬스체크를 실행한다.

        각 컴포넌트별로 ping/get_balance 등을 호출하여 상태를 확인한다.
        하나라도 실패하면 healthy=False.

        Returns:
            {"healthy": bool, "timestamp": str, "<component>": {"status": str, "message": str}}.
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "healthy": True,
        }

        for name, component in self.components.items():
            try:
                self._check_component(name, component)
                result[name] = {"status": "ok", "message": ""}
            except Exception as e:
                result[name] = {"status": "error", "message": str(e)}
                result["healthy"] = False
                logger.warning("헬스체크 실패: %s — %s", name, e)

        return result

    def _check_component(self, name: str, component) -> None:
        """개별 컴포넌트 상태를 확인한다.

        브로커는 get_balance(), 나머지는 ping()을 호출한다.

        Args:
            name: 컴포넌트 이름.
            component: 컴포넌트 인스턴스.

        Raises:
            Exception: 연결 실패 시.
        """
        if name == "broker":
            component.get_balance()
        elif hasattr(component, "ping"):
            component.ping()
        elif hasattr(component, "check_health"):
            component.check_health()
        # ping/check_health 메서드가 없는 컴포넌트는 건너뜀
