"""ContentReader — ./reports/*.md 디렉토리 스캔 + YAML frontmatter 파싱.

Read-only. 실제 리포트 쓰기는 `alphapulse.content.reporter.ReportWriter` 가 담당.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Literal, TypedDict

import yaml

logger = logging.getLogger(__name__)


class ReportMeta(TypedDict):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str


class ReportFull(ReportMeta):
    body: str


class ListResult(TypedDict):
    items: list[ReportMeta]
    total: int
    page: int
    size: int
    categories: list[str]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """마크다운 텍스트에서 frontmatter + body 분리.

    frontmatter 가 없거나 파싱 실패 시 (빈 dict, 원본 텍스트).
    """
    if not text.startswith("---"):
        return {}, text
    # 첫 줄 이후 --- 까지 찾기
    lines = text.split("\n")
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx < 0:
        return {}, text
    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    try:
        meta = yaml.safe_load(yaml_text) or {}
        if not isinstance(meta, dict):
            logger.warning("frontmatter 가 dict 가 아님: %r", meta)
            return {}, body
        return meta, body
    except yaml.YAMLError as e:
        logger.warning("YAML 파싱 실패: %s", e)
        return {}, body


def _wrap_mark_snippet(text: str, term: str, context_chars: int = 16) -> str:
    """텍스트에서 term 첫 번째 위치를 <mark>로 감싼 스니펫 반환.

    FTS5 snippet() 과 동일한 형태로 LIKE 폴백 결과를 포맷한다.
    매치 없으면 텍스트 앞 60자를 반환.
    """
    if not text or not term:
        return ""
    lower = text.lower()
    pos = lower.find(term.lower())
    if pos < 0:
        return text[:60]
    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(term) + context_chars)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    before = text[start:pos]
    matched = text[pos:pos + len(term)]
    after = text[pos + len(term):end]
    return f"{prefix}{before}<mark>{matched}</mark>{after}{suffix}"


def _sanitize_fts_query(raw):
    """사용자 입력을 FTS5 MATCH 로 안전하게 변환.

    특수문자 `"`, `*`, `:`, `(`, `)` 를 공백으로 치환 후 phrase 로 감싼다.
    빈 문자열이면 "" 반환.
    """
    cleaned = re.sub(r'["*:()\[\]]', ' ', raw or "").strip()
    if not cleaned:
        return ""
    return f'"{cleaned}"'


def _read_body(path):
    """`.md` 파일에서 frontmatter(`---...---`) 를 제거한 본문 반환.

    파일 없으면 빈 문자열. frontmatter 없으면 전체 텍스트.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    if not text.startswith("---"):
        return text
    # `---` 이후 다음 `\n---` 위치 탐색
    rest = text[3:]
    close_idx = rest.find("\n---")
    if close_idx < 0:
        return text
    after = rest[close_idx + len("\n---"):]
    return after.lstrip("\r\n")


def _meta_from_file(path: Path) -> ReportMeta:
    """파일에서 frontmatter 파싱. 실패 시 fallback."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        logger.warning("파일 읽기 실패 %s: %s", path, e)
        text = ""
    fm, _body = _parse_frontmatter(text)
    return {
        "filename": path.name,
        "title": str(fm.get("title") or path.stem),
        "category": str(fm.get("category") or "미분류"),
        "published": str(fm.get("published") or ""),
        "analyzed_at": str(fm.get("analyzed_at") or ""),
        "source": str(fm.get("source") or ""),
        "source_tag": str(fm.get("source_tag") or ""),
    }


def _date_in_range(
    published: str, date_from: str | None, date_to: str | None,
) -> bool:
    """published(YYYY-MM-DD 또는 YYYYMMDD) 가 date_from~date_to 범위에 있는지."""
    if not date_from and not date_to:
        return True
    if not published:
        return False
    normalized = published.replace("-", "").replace(".", "")[:8]
    if not normalized.isdigit() or len(normalized) != 8:
        return False
    if date_from and normalized < date_from:
        return False
    if date_to and normalized > date_to:
        return False
    return True


class ContentReader:
    """./reports/*.md 읽기 전용 리더."""

    def __init__(
        self,
        reports_dir: Path | str,
        fts_db_path: Path | str | None = None,
    ) -> None:
        self.reports_dir = Path(reports_dir)
        self.fts_db = Path(fts_db_path) if fts_db_path else None
        self._scan_cache: list[ReportMeta] | None = None
        self._scan_cache_mtime: float | None = None
        self._fts_available = False
        if self.fts_db is not None:
            self._init_fts_schema()

    def _init_fts_schema(self) -> None:
        """FTS5 가상 테이블 + meta 테이블 생성 (idempotent).

        FTS5 모듈 미지원 SQLite 빌드에서는 조용히 실패하고
        ``_fts_available = False`` 유지.
        """
        try:
            self.fts_db.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.fts_db) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reports_meta (
                        filename TEXT PRIMARY KEY,
                        mtime REAL NOT NULL,
                        indexed_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
                        filename UNINDEXED,
                        title,
                        category,
                        body,
                        tokenize = 'trigram'
                    )
                    """
                )
            self._fts_available = True
        except sqlite3.OperationalError as e:
            logger.warning("content_search: FTS5 init failed — %s", e)
            self._fts_available = False

    def upsert_index(self, filename: str) -> None:
        """단일 파일을 FTS5 인덱스에 반영 (upsert)."""
        if not self._fts_available or self.fts_db is None:
            return
        path = self.reports_dir / filename
        if not path.is_file():
            return
        meta = _meta_from_file(path)
        body = _read_body(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        with sqlite3.connect(self.fts_db) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "DELETE FROM reports_fts WHERE filename = ?", (filename,)
                )
                conn.execute(
                    "DELETE FROM reports_meta WHERE filename = ?", (filename,)
                )
                conn.execute(
                    "INSERT INTO reports_fts (filename, title, category, body) "
                    "VALUES (?, ?, ?, ?)",
                    (filename, meta["title"], meta["category"], body),
                )
                conn.execute(
                    "INSERT INTO reports_meta (filename, mtime, indexed_at) "
                    "VALUES (?, ?, ?)",
                    (filename, mtime, time.time()),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def build_index(self) -> dict:
        """디스크와 FTS5 인덱스를 mtime 기반으로 동기화.

        Returns: {"added": N, "updated": N, "removed": N}
        """
        if not self._fts_available or self.fts_db is None:
            return {"added": 0, "updated": 0, "removed": 0}
        if not self.reports_dir.is_dir():
            return {"added": 0, "updated": 0, "removed": 0}

        disk: dict[str, float] = {}
        for entry in self.reports_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".md" or entry.name.startswith("."):
                continue
            try:
                disk[entry.name] = entry.stat().st_mtime
            except OSError:
                continue

        with sqlite3.connect(self.fts_db) as conn:
            rows = conn.execute(
                "SELECT filename, mtime FROM reports_meta"
            ).fetchall()
        db = {r[0]: r[1] for r in rows}

        added = [n for n in disk if n not in db]
        updated = [n for n in disk if n in db and db[n] != disk[n]]
        removed = [n for n in db if n not in disk]

        for name in added + updated:
            try:
                self.upsert_index(name)
            except Exception as e:
                logger.warning("build_index upsert failed for %s: %s", name, e)

        if removed:
            with sqlite3.connect(self.fts_db) as conn:
                conn.executemany(
                    "DELETE FROM reports_fts WHERE filename = ?",
                    [(n,) for n in removed],
                )
                conn.executemany(
                    "DELETE FROM reports_meta WHERE filename = ?",
                    [(n,) for n in removed],
                )

        return {"added": len(added), "updated": len(updated), "removed": len(removed)}

    def _scan(self) -> list[ReportMeta]:
        if not self.reports_dir.is_dir():
            # 디렉터리 없음 → 캐시 무효화 + 빈 반환
            self._scan_cache = None
            self._scan_cache_mtime = None
            return []

        try:
            dir_mtime = self.reports_dir.stat().st_mtime
        except OSError:
            dir_mtime = None

        if (
            self._scan_cache is not None
            and dir_mtime is not None
            and self._scan_cache_mtime == dir_mtime
        ):
            return self._scan_cache

        metas: list[ReportMeta] = []
        for entry in self.reports_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".md":
                continue
            if entry.name.startswith("."):
                continue
            metas.append(_meta_from_file(entry))

        self._scan_cache = metas
        self._scan_cache_mtime = dir_mtime
        return metas

    def list_reports(
        self,
        *,
        categories: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        query: str | None = None,
        sort: Literal["newest", "oldest"] = "newest",
        page: int = 1,
        size: int = 20,
    ) -> ListResult:
        # FTS 가능 + query 있으면 search() 로 위임
        if query and self._fts_available:
            return self.search(
                q=query, categories=categories,
                date_from=date_from, date_to=date_to,
                page=page, size=size,
            )

        all_metas = self._scan()
        # 필터
        filtered = [
            m for m in all_metas
            if (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
            and (not query or query.lower() in m["title"].lower())
        ]
        # 정렬 (analyzed_at 기준)
        reverse = sort == "newest"
        filtered.sort(key=lambda m: m["analyzed_at"], reverse=reverse)
        # 페이지네이션
        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        items = filtered[start:end]
        # 전체 파일 기준 distinct 카테고리
        categories_all = sorted({m["category"] for m in all_metas})
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "categories": categories_all,
        }

    def get_report(self, filename: str) -> ReportFull | None:
        path = self.reports_dir / filename
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            logger.warning("파일 읽기 실패 %s: %s", path, e)
            return None
        fm, body = _parse_frontmatter(text)
        return {
            "filename": path.name,
            "title": str(fm.get("title") or path.stem),
            "category": str(fm.get("category") or "미분류"),
            "published": str(fm.get("published") or ""),
            "analyzed_at": str(fm.get("analyzed_at") or ""),
            "source": str(fm.get("source") or ""),
            "source_tag": str(fm.get("source_tag") or ""),
            "body": body,
        }

    def search(
        self,
        *,
        q,
        categories,
        date_from,
        date_to,
        page,
        size,
    ) -> dict:
        """FTS5 기반 검색 + 메타 필터 + rank 정렬 + 페이지네이션."""
        all_metas = self._scan()
        categories_all = sorted({m["category"] for m in all_metas})
        q_sanitized = _sanitize_fts_query(q)
        if not q_sanitized or not self._fts_available or self.fts_db is None:
            return {
                "items": [], "total": 0, "page": page, "size": size,
                "categories": categories_all,
            }

        cleaned_q = re.sub(r'["*:()\[\]]', ' ', q or "").strip()
        try:
            with sqlite3.connect(self.fts_db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT
                        filename,
                        snippet(reports_fts, 3, '<mark>', '</mark>', '…', 16) AS highlight,
                        bm25(reports_fts) AS rank
                    FROM reports_fts
                    WHERE reports_fts MATCH ?
                    ORDER BY rank
                    """,
                    (q_sanitized,),
                ).fetchall()
                # FTS5 trigram requires ≥3 chars; fall back to LIKE for short queries
                if not rows and cleaned_q:
                    escaped = (
                        cleaned_q
                        .replace("\\", "\\\\")
                        .replace("%", "\\%")
                        .replace("_", "\\_")
                    )
                    like_pat = f"%{escaped}%"
                    like_rows = conn.execute(
                        """
                        SELECT
                            filename,
                            title,
                            body,
                            0.0 AS rank
                        FROM reports_fts
                        WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\'
                        """,
                        (like_pat, like_pat),
                    ).fetchall()
                    # body를 우선해 highlight 생성; body에 없으면 title에서 추출
                    built = []
                    for r in like_rows:
                        body_hl = _wrap_mark_snippet(r["body"], cleaned_q)
                        title_hl = _wrap_mark_snippet(r["title"], cleaned_q)
                        highlight = body_hl if "<mark>" in body_hl else title_hl
                        built.append({
                            "filename": r["filename"],
                            "highlight": highlight,
                            "rank": r["rank"],
                        })
                    rows = built
        except sqlite3.OperationalError as e:
            logger.warning("content_search MATCH failed for %r: %s", q, e)
            rows = []

        match_by_name = {r["filename"]: dict(r) for r in rows}
        filtered = [
            m for m in all_metas
            if m["filename"] in match_by_name
            and (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
        ]
        filtered.sort(key=lambda m: match_by_name[m["filename"]]["rank"])
        total = len(filtered)
        start = (page - 1) * size
        items = [
            {**m, "highlight": match_by_name[m["filename"]]["highlight"]}
            for m in filtered[start:start + size]
        ]
        return {
            "items": items, "total": total, "page": page, "size": size,
            "categories": categories_all,
        }

    def distinct_categories(self) -> list[str]:
        return sorted({m["category"] for m in self._scan()})
