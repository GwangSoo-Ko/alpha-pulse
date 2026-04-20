"""webapp 테스트 공통 fixture."""
from pathlib import Path

import pytest

from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def webapp_db(tmp_path: Path) -> Path:
    """빈 스키마로 초기화된 임시 webapp.db 경로."""
    db_path = tmp_path / "webapp.db"
    init_webapp_db(db_path)
    return db_path
