# Content FTS5 전문 검색 — Design Spec

**작성일**: 2026-04-23
**대상 페이지**: `/content`
**목표**: 제목 + 본문 키워드 검색 + 하이라이트 + 랭킹. 기존 `.md` 파일 저장 구조 유지.

---

## 1. 원칙

- **Shadow index**: `.md` 파일이 SSOT. SQLite FTS5 는 검색 전용 derived. 인덱스 drift 는 rebuild 로 복구.
- **Trigram tokenizer**: 한글 조사/어미 우회, 부분 문자열 매칭. 외부 의존성 없음.
- **인덱스 라이프사이클**: 앱 시작 시 mtime-diff rebuild + 파일 저장 시 incremental upsert.
- **API 호환**: 기존 `GET /api/v1/content/reports?q=...` 시그니처 유지. 응답에 `highlight: str | None` 필드 추가.
- **Graceful degradation**: FTS5 기능 부재/오류 시 서버 시작은 계속, 검색 기능만 빈 결과.

## 2. 데이터 모델

### 2.1 신규 SQLite DB: `content_search.db`

경로: `Config().DATA_DIR / "content_search.db"` (다른 DB 와 동일 패턴).

### 2.2 스키마

```sql
CREATE TABLE reports_meta (
    filename TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE VIRTUAL TABLE reports_fts USING fts5(
    filename UNINDEXED,
    title,
    category,
    body,
    tokenize = 'trigram'
);
```

**왜 content-own (external content 안 씀)**: rowid 매핑 복잡도 회피. `reports_meta` 는 mtime 추적 전용, `reports_fts` 가 실제 인덱스 + 원본 재료 모두 보관. 두 테이블 동기화는 upsert 시 단일 트랜잭션.

## 3. 주요 API 및 로직

### 3.1 `ContentReader` 확장 (`alphapulse/webapp/store/readers/content.py`)

**생성자 변경**:

```python
class ContentReader:
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
```

**신규 메서드**:

- `_init_fts_schema() -> None` — 테이블 생성 (idempotent). FTS5 모듈 없으면 `_fts_available = False` 유지, 예외 무시.
- `build_index() -> dict` — `{added, updated, removed}` 반환. 앱 시작 시 호출.
- `upsert_index(filename: str) -> None` — 단일 파일 재인덱싱 (저장 경로에서 호출).
- `_remove_from_index(filename: str) -> None` — build_index 내부에서 사용.
- `search(q, categories, date_from, date_to, page, size) -> dict` — FTS5 기반 검색 + category/date 후필터 + rank 정렬 + 페이지네이션.

**기존 `list_reports(query=...)` 변경**:
- `query` 파라미터는 유지.
- `query` 값 있고 `_fts_available` 이면 `search()` 위임.
- 없거나 FTS 불가 시 기존 경로 (substring fallback).

### 3.2 Search 쿼리 핵심

```python
def search(self, *, q, categories, date_from, date_to, page, size):
    q_sanitized = _sanitize_fts_query(q)
    if not q_sanitized or not self._fts_available:
        return {"items": [], "total": 0, "page": page, "size": size,
                "categories": sorted({m["category"] for m in self._scan()})}
    try:
        with sqlite3.connect(self.fts_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT filename,
                       snippet(reports_fts, 3, '<mark>', '</mark>', '…', 16) AS highlight,
                       bm25(reports_fts) AS rank
                FROM reports_fts WHERE reports_fts MATCH ?
                ORDER BY rank
                """,
                (q_sanitized,),
            ).fetchall()
    except sqlite3.OperationalError as e:
        logger.warning("FTS5 syntax error for %r: %s", q, e)
        rows = []

    match_by_name = {r["filename"]: dict(r) for r in rows}
    all_metas = self._scan()
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
        "categories": sorted({m["category"] for m in all_metas}),
    }
```

### 3.3 `_sanitize_fts_query`

```python
def _sanitize_fts_query(raw: str) -> str:
    """사용자 입력을 FTS5 MATCH 로 안전하게 변환.

    FTS5 특수문자(`"`, `*`, `:`, `(`, `)`) 를 공백으로 치환 후,
    전체를 phrase 로 감싸 MATCH syntax error 회피.
    빈 문자열이면 "" 반환 (호출부가 FTS 건너뜀).
    """
    cleaned = re.sub(r'["\*\:\(\)]', ' ', raw or '').strip()
    if not cleaned:
        return ''
    return f'"{cleaned}"'
```

Phrase 로 감싸면 trigram 토크나이저는 내부 3-gram 을 AND 로 매칭, 한글 부분 문자열 검색이 자연스럽게 동작.

### 3.4 Build 로직

```python
def build_index(self) -> dict:
    if not self._fts_available or not self.reports_dir.is_dir():
        return {"added": 0, "updated": 0, "removed": 0}
    disk = {
        e.name: e.stat().st_mtime
        for e in self.reports_dir.iterdir()
        if e.suffix == ".md" and not e.name.startswith(".")
    }
    with sqlite3.connect(self.fts_db) as conn:
        rows = conn.execute("SELECT filename, mtime FROM reports_meta").fetchall()
    db = {r[0]: r[1] for r in rows}

    added = [n for n in disk if n not in db]
    updated = [n for n in disk if n in db and db[n] != disk[n]]
    removed = [n for n in db if n not in disk]

    for name in added + updated:
        try:
            self.upsert_index(name)
        except Exception as e:
            logger.warning("upsert_index failed for %s: %s", name, e)

    if removed:
        with sqlite3.connect(self.fts_db) as conn:
            conn.executemany(
                "DELETE FROM reports_fts WHERE filename = ?", [(n,) for n in removed]
            )
            conn.executemany(
                "DELETE FROM reports_meta WHERE filename = ?", [(n,) for n in removed]
            )
    return {"added": len(added), "updated": len(updated), "removed": len(removed)}
```

### 3.5 Upsert 단일 파일

```python
def upsert_index(self, filename: str) -> None:
    if not self._fts_available:
        return
    path = self.reports_dir / filename
    if not path.is_file():
        return
    meta = _meta_from_file(path)
    body = _read_body(path)
    mtime = path.stat().st_mtime
    with sqlite3.connect(self.fts_db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM reports_fts WHERE filename = ?", (filename,))
            conn.execute("DELETE FROM reports_meta WHERE filename = ?", (filename,))
            conn.execute(
                "INSERT INTO reports_fts (filename, title, category, body) VALUES (?, ?, ?, ?)",
                (filename, meta["title"], meta["category"], body),
            )
            conn.execute(
                "INSERT INTO reports_meta (filename, mtime, indexed_at) VALUES (?, ?, ?)",
                (filename, mtime, time.time()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
```

### 3.6 `_read_body(path)` 헬퍼

Frontmatter(`---...---`) 제거 후 본문 반환. 기존 `_parse_frontmatter` 재사용 또는 간단 split.

## 4. 통합 지점

### 4.1 Config 확장

`alphapulse/core/config.py` 에 추가:

```python
@property
def CONTENT_SEARCH_DB(self) -> Path:
    return self.DATA_DIR / "content_search.db"
```

### 4.2 앱 시작 훅

`alphapulse/webapp/main.py` 의 `create_app()`:

```python
reader = ContentReader(
    reports_dir=cfg.CONTENT_REPORTS_DIR,
    fts_db_path=cfg.CONTENT_SEARCH_DB,
)
app.state.content_reader = reader
try:
    stats = reader.build_index()
    logger.info("content_search index built: %s", stats)
except Exception as e:
    logger.warning("content_search index build failed: %s", e)
```

### 4.3 파일 저장 시 incremental upsert

`alphapulse/content/monitor.py` 가 `ReportWriter.save()` 로 파일을 저장한 뒤 filepath 를 받음. 그 직후:

```python
filepath = self.reporter.save(...)
try:
    from alphapulse.webapp.store.readers.content import ContentReader
    ContentReader(
        reports_dir=self.reporter.reports_dir,
        fts_db_path=Config().CONTENT_SEARCH_DB,
    ).upsert_index(filepath.name)
except Exception as e:
    logger.warning("content_search upsert failed for %s: %s", filepath.name, e)
```

**원칙**: 인덱스 실패가 리포트 저장을 중단시키지 않도록 try/except (CLAUDE.md 피드백 원칙과 동일).

### 4.4 API 응답 모델

`alphapulse/webapp/api/content.py`:

```python
class ReportSummary(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    highlight: str | None = None
```

기존 소비자(FE) 는 `highlight` 무시 → default None 으로 비즈니스 영향 없음.

### 4.5 Frontend — ReportsTable 하이라이트 row

`webapp-ui/components/domain/content/report-summary-row.tsx` 타입 확장 + `reports-table.tsx` 에서 highlight 존재 시 colspan row 렌더.

**렌더 방식**: `snippet()` 결과는 HTML 문자열 (`<mark>...</mark>`) 이므로 raw HTML 삽입 필요. React 에서는 `dangerouslySetInnerHTML` API 가 유일한 방법.

**XSS 위험도 평가**: `highlight` 콘텐츠는 두 단계 모두 서버가 통제.
1. 원본 본문: `.md` 파일 (리포트 생성기가 작성, 사용자 자유 입력 없음).
2. 하이라이트 생성: SQLite `snippet()` 함수가 `<mark>` 태그를 삽입 (결정론적, 다른 태그 생성 안 함).

현실적 위험 낮지만 방어적으로 **검토 포인트**:
- 향후 `.md` 파일 출처가 확장되어 사용자 제출 컨텐츠 포함 시 — `dompurify` 또는 `html-react-parser` 로 `<mark>` 만 화이트리스트.
- 이번 PR 에서는 `dangerouslySetInnerHTML` 사용 정당화: 범위 밖 위험 확장 시에만 sanitize 추가.

```tsx
{item.highlight && (
  <tr>
    <td colSpan={4} className="px-3 pb-2 text-xs text-neutral-400">
      <span
        className="[&_mark]:bg-yellow-700/40 [&_mark]:text-yellow-200 [&_mark]:rounded [&_mark]:px-0.5"
        dangerouslySetInnerHTML={{ __html: item.highlight }}
      />
    </td>
  </tr>
)}
```

## 5. 에러 처리

| 상황 | 동작 |
|---|---|
| FTS5 모듈 미지원 (SQLite 빌드) | `_init_fts_schema` 가 OperationalError catch → `_fts_available=False`. search 는 빈 결과 반환. |
| DB 파일 없음 | `_init_fts_schema` 가 idempotent CREATE — 자동 생성. |
| `build_index` 전체 실패 | warning 로그, 시작은 계속. |
| `upsert_index` 개별 파일 실패 | warning 로그, 다른 파일은 계속. |
| MATCH 쿼리 syntax error | try/except OperationalError → 빈 결과 + `highlight=None`. |
| 빈 `q` | FTS 건너뜀, 기존 필터/정렬 경로. |
| FTS 특수문자 (`"`, `*`, `:`, `(`, `)`) 포함 | `_sanitize_fts_query` 가 공백 치환 후 phrase wrap. |
| 파일 디스크엔 있으나 인덱스 누락 (drift) | 검색 누락. 앱 재시작 시 `build_index` 가 복구. 수동 rebuild 엔드포인트는 YAGNI. |

## 6. 테스트

### 6.1 신규: `tests/webapp/store/readers/test_content_search.py`

- `test_build_index_from_empty_disk_noop`
- `test_build_index_indexes_new_files`
- `test_build_index_detects_mtime_change`
- `test_build_index_removes_missing_files`
- `test_upsert_index_replaces_existing`
- `test_search_matches_title`
- `test_search_matches_body`
- `test_search_trigram_matches_korean_with_particles` (예: 입력 "삼성전자" → 본문 "삼성전자가..." 매칭)
- `test_search_returns_highlight_with_mark_tags`
- `test_search_sanitizes_fts_special_chars` (`"`, `*`, `:`, `(`, `)` 포함 쿼리)
- `test_search_syntax_error_returns_empty`
- `test_search_filters_by_category_after_fts`
- `test_search_filters_by_date_range_after_fts`
- `test_search_sorts_by_bm25_rank`
- `test_search_paginates_after_rank`

### 6.2 API 회귀: `tests/webapp/api/test_content.py`

- `test_list_reports_with_q_includes_highlight` — highlight 필드 `<mark>` 포함
- `test_list_reports_without_q_no_highlight` — highlight None
- 기존 필터/페이지네이션 테스트 회귀

### 6.3 FE E2E: `webapp-ui/e2e/content.spec.ts` 확장

- 검색어 입력 → 테이블 표시 + `mark` 요소 가시성 확인 (seed 데이터 있을 때 실행, 없으면 `test.skip`)

## 7. 성공 기준

- pytest 1287 + 17 = 1304+ 통과
- ruff clean
- pnpm lint / pnpm build 성공
- 수동: "삼성전자" 검색 → 본문에 "삼성전자가/의" 포함된 리포트 매칭 + 하이라이트 렌더

## 8. 범위 밖

- 본문 외 첨부 파일 검색 (PDF/이미지)
- 사용자별 검색 히스토리
- 검색어 자동완성
- 다국어 형태소 분석 (mecab-ko)
- 수동 `/rebuild-index` 엔드포인트
- external content FTS5
- 파일시스템 watchdog (실시간 감지)
- HTML sanitizer 도입 (원본 출처가 사용자 입력 확장 시)
