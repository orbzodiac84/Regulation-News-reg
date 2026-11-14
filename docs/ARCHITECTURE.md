# System Architecture (As-Built)

**Version**: 1.0.0
**Context**: MarketPulse-Reg (Regulatory News Analysis)
**Status**: Round 6-8 hardening complete

## 1. High-Level Architecture
The system follows a **Serverless Event-Driven** pattern using GitHub Actions as the primary execution environment.

```mermaid
graph TD
    Trigger[External Cron · cron-job.org] -->|workflow_dispatch| GHA[news_collector_v2_active.yml]
    GHA --> Main[src/main.py]
    Main --> Pipeline[src/pipeline.py]
    
    subgraph Data Collection
        Pipeline -->|Fetch| Scraper[src/collectors/scraper.py]
        Pipeline -->|Fetch| RSS[src/collectors/rss_parser.py]
    end
    
    subgraph Analysis Layer
        Pipeline -->|Raw Text| Analyzer[src/services/analyzer/*]
        Analyzer -->|Gemini 2.5| Tier1[Gatekeeper]
        Analyzer -->|Gemini 3.0| Tier2[Analyst]
        Analyzer -->|Keywords| Safeguard[Safeguard Rules]
    end
    
    subgraph Persistence & Alert
        Pipeline -->|Insert| Supabase[src/db/client.py]
        Pipeline -->|Notify| Telegram[src/services/notifier.py]
    end
```

---

## 2. Directory Structure (File Map)
This map reflects the **actual** codebase after round 1 refactor.

```
reg_brief/
├── .github/
│   └── workflows/
│       └── news_collector_v2_active.yml  # Production collector (triggered by external cron-job.org via workflow_dispatch)
├── config/
│   ├── agencies.json           # Target Agency Config (single source of truth)
│   └── safeguard_keywords.json # Keyword Override Rules
├── docs/                       # Documentation Assets
├── db/
│   └── schema.sql              # v1 schema snapshot (see Schema status below)
├── scripts/
│   └── v2_schema_setup.sql     # v2 schema snapshot (see Schema status below)
├── src/
│   ├── collectors/
│   │   ├── http.py             # HTTP fetch helpers
│   │   ├── date_parser.py      # Date normalization
│   │   ├── pagination.py       # Pagination helpers
│   │   ├── list_scraper.py     # List page scraping
│   │   ├── content_scraper.py  # Detail page scraping
│   │   ├── sanction_scraper.py # FSS sanction scraping
│   │   ├── rss_parser.py       # RSS parsing
│   │   └── scraper.py          # Facade
│   ├── config/
│   │   ├── settings.py         # Constants + env loading (Gemini model IDs via env)
│   │   ├── agency_codes.py     # Agency code constants (enum)
│   │   └── agency_loader.py    # Runtime-derived agency metadata (sanction codes)
│   ├── db/
│   │   └── client.py           # Supabase Connection
│   ├── services/
│   │   ├── analyzer/           # Hybrid analyzer package (see 4.1)
│   │   │   ├── hybrid.py
│   │   │   ├── prompts.py
│   │   │   ├── gemini_client.py
│   │   │   ├── result_mapper.py
│   │   │   └── safeguards.py
│   │   └── notifier.py         # Telegram Bot Logic
│   ├── utils/
│   │   ├── logger.py           # Centralized Logging
│   │   └── preserve.py         # analysis_result 키 보존 헬퍼 (admin/backfill 스크립트용)
│   ├── main.py                 # [Entry Point] Production Runner
│   └── pipeline.py             # [Core] Orchestration Logic
└── web/                        # Frontend (Next.js)
    ├── app/
    │   ├── page.tsx            # Live entry → DashboardV2
    │   ├── login/              # Login page
    │   └── api/
    │       ├── auth/login/     # Passcode → mp_session cookie
    │       └── report/         # Report endpoint (auth-guarded)
    ├── components/
    │   └── dashboard/
    │       ├── DashboardV2.tsx       # Live entry. round6-8에서 Sidebar/AgencyIcon/constants/useHasNewByCategory 등으로 분해됨
    │       └── ...                   # Header, NewsCard, SearchBar, StarRating, DateSection 등 기존 컴포넌트 유지
    ├── lib/
    │   ├── auth.ts             # HMAC session cookie helpers
    │   ├── prompts/report.ts   # buildReportPrompt() — report prompt template
    │   └── validation/report.ts # /api/report request schema
    ├── __tests__/              # vitest suites (api + lib)
    └── proxy.ts                # Route protection (mp_session cookie guards /api/*)
```

Tests live in `tests/unit/**` (pytest) and `web/__tests__/**` (vitest); both
are executed on PRs by `.github/workflows/ci.yml` (`python-test`,
`web-test`, `gitleaks` jobs).

The configured agency count is the length of the `agencies` array in
`config/agencies.json` (single source of truth).

---

## 3. Data Flow (Pipeline)
1.  **Collection**: `main.py` triggers `pipeline.run()`. Scrapers fetch data from agencies.
2.  **Deduplication**: `pipeline._is_duplicate()` checks `link` against DB.
3.  **Processing**:
    - **Step 1**: Tier 1 filter (Gemini 2.5) -> Score 0-5.
    - **Step 2**: Keyword safeguards -> Force Score 4/5 if keyword matches.
    - **Step 3**: Tier 2 analysis (Gemini 3.0) -> Runs only if Score >= threshold.
4.  **Storage**: `pipeline._save_item()` inserts JSON payload to Supabase.
    `pdf_url`이 있는 항목(주로 sanction)은 insert 직전에 `analysis_result` JSON 안으로 merge되어 단일 컬럼에 저장된다.
5.  **Alerting**: `notifier.format_and_send()` sends Telegram msg ONLY if `analysis_result` exists.

## 4. Key Components Detail

### 4.1 Hybrid Analyzer (`src/services/analyzer/`)
After round 1 refactor, the analyzer is a package, not a single file. Each
module owns a single responsibility; refer to the source for current
signatures.

- `hybrid.py` — orchestrates the 2-Tier + Safeguard strategy.
- `prompts.py` — prompt templates for Tier 1/Tier 2.
- `gemini_client.py` — Gemini API client wrapper. round5에서 `google-genai` SDK 기반으로 마이그레이션. 회귀 테스트는 `tests/unit/analyzer/test_gemini_client.py`.
- `result_mapper.py` — maps raw model output to internal result shape.
- `safeguards.py` — keyword-based score override rules.

Backend Gemini model IDs are env-driven via `src/config/settings.py`:
`GEMINI_FILTER_MODEL` (Tier 1), `GEMINI_ANALYZER_MODEL` (Tier 2), and
`GEMINI_ANALYZER_FALLBACK_MODEL` (Tier 2 fallback). Defaults live in
`settings.py`. The frontend `/api/report` route uses a separate
`GEMINI_REPORT_MODEL` env (default in `web/app/api/report/route.ts`).
Gemini calls are fail-closed behind `GEMINI_ENABLED`: unless the value is
explicitly set to `true`/`1`/`yes`/`on`, backend analysis and the web
`/api/report` route do not create Gemini SDK clients even when
`GEMINI_API_KEY` is present.

### 4.1.1 Sanction agency derivation
`SANCTION_AGENCY_CODES` is no longer a hardcoded frozenset. It is derived
at runtime by `src/config/agency_loader.get_sanction_codes()` from the
`category` field of `config/agencies.json` (entries with
`category == "sanction_notice"`). Adding a new sanction source therefore
requires only a JSON edit. 동일 모듈의 `get_ssl_verify(code)`도 같은 패턴으로
per-agency TLS verify 정책을 단일 진실원(`config/agencies.json`)에서 도출한다.

### 4.1.2 SSL verification policy
- 기본값: `src/config/settings.py`의 `SSL_VERIFY = True` (round6에서 `False`→`True`로 반전).
- per-agency opt-out: `config/agencies.json`의 `ssl_verify: false` 필드.
- 적용: `src/collectors/sanction_scraper.py`가 `agency_loader.get_ssl_verify(code)`로
  값을 읽어 `http.fetch(url, verify=...)`에 전달.
- 검증: `.github/workflows/ssl-matrix-check.yml`이 verify on/off 매트릭스로 회귀를 점검.

### 4.1.3 List link canonicalization
- per-agency opt-in: `config/agencies.json`의 `link_strip_query: true` 필드.
- 적용: `src/collectors/list_scraper.canonicalize_link()`가 목록에서 얻은 상세 링크의
  query/fragment를 제거한다. FSC 보도자료 목록은 상세 링크에 `curPage=N`을 붙이므로,
  제거하지 않으면 같은 글이 2페이지로 밀릴 때 다른 링크가 되어 link 기반 dedup이 깨진다.
- 상세 링크 식별자가 query에 있는 기관(예: FSC_REG `view?noticeId=`)은 켜면 안 된다.
- 페이지 번호 정규화(전 기관 공통): FSS·BOK·FSS_REG·FSC_REG는 현재 목록 페이지 번호를
  상세 링크에 넣는다(`pageIndex=N` / `curPage=N`). `pagination.normalize_page_param()`이
  N>1 페이지에서 얻은 링크를 1페이지 형태(`=1`, 1페이지는 항상 명시적 `=1`로 요청)로 되돌린다.
  없으면 2페이지 이후의 같은 글이 다른 링크가 되어 중복 저장된다(2026-11-03 19건).
- JS 링크 게시판: `link_id_pattern` + `link_template`(agencies.json)으로 상세 URL을 만든다
  (MOEF `javascript:fn_egov_select('MOSF_…')`).

### 4.1.4 List cutoff (언제 페이지 넘김을 멈추나)
- `list_scraper.compute_cutoff()`: `max(가장 최근 저장 published_at − 1일, 지금 − 7일)`을
  **KST 자정으로 내림**. 목록은 날짜만 보여주므로 시각 기준 컷오프는 게시판이 전날 날짜로
  늦게 올린 글을 영구 누락시킨다(MOEF에서 관찰). 겹치는 구간은 link dedup이 걸러낸다.
- 페이지 상한(`MAX_PAGES`=15)에 걸려 컷오프에 못 미치면 `WINDOW_OVERFLOW`로 보고한다.
- 정기 수집은 7일보다 오래된 글을 보지 않는다. 그보다 긴 공백은 `scripts/admin/backfill_press.py`.

### 4.1.5 Source health (죽은 소스 감지)
- 수집기는 실패해도 `[]`를 반환해 사이클을 계속 돈다. 그래서 2026-07 korea.kr RSS 종료 후
  MOEF가 4개월간 매 실행 404였는데도 실행은 모두 성공으로 보였다.
- `src/collectors/source_health.py`: 수집기가 `FETCH_ERROR`(HTTP/연결 실패), `EMPTY`(항목 0 /
  셀렉터 불일치), `STALE`(RSS 최신 항목 14일 초과), `WINDOW_OVERFLOW`(RSS 창 전체가 미저장 /
  페이지 상한 도달)를 기록한다.
- `Pipeline.run()` 끝에서 로그 요약 + GitHub Actions annotation을 남기고, KST 09:00~09:29에
  시작한 실행만 텔레그램 요약을 보낸다(하루 1회, `settings.SOURCE_HEALTH_DIGEST_*`).

### 4.1.6 Dedup state fail-closed
- `_load_existing_links` / `_load_sanction_keys` 실패 시 `DedupStateUnavailable`로 사이클을
  중단한다(수집 요청 전). 빈 캐시로 진행하면 모든 글이 신규로 처리된다: 2026-11-03 Supabase
  400 한 번에 7일치 재스캔, 상세 페이지 대량 요청(mafra.go.kr가 연결을 끊음), 중복 19건 저장.

### 4.1.7 Backfill / dedupe tools (`scripts/admin/`)
- `backfill_press.py --agency X --since YYYY-MM-DD [--apply]`: 목록을 4~7초 간격으로 넘기며
  누락분 INSERT, 수집 시각으로 잘못 찍힌 행 REDATE. 기본 dry-run. RSS 기관은
  agencies.json의 `list_fallback`(HTML 목록) 사용.
- `dedupe_page_links.py [--apply]`: 페이지 번호 링크로 생긴 중복 중 1페이지 쌍둥이가 있는 행만 삭제.
- 운영 자격증명으로 실행: `.github/workflows/admin-backfill.yml` (workflow_dispatch).

### 4.2 Supabase Client (`src/db/client.py`)
- **Responsibility**: Singleton connection to PostgreSQL.
- **Connection Logic**:
    - Backend collectors use `SUPABASE_URL`.
    - Write-capable backend paths prefer `SUPABASE_SERVICE_ROLE_KEY`.
    - If `SUPABASE_SERVICE_ROLE_KEY` is absent, the client falls back to `SUPABASE_ANON_KEY` for local/development compatibility. Hardened production RLS does not allow anon writes.
    - Frontend dashboard clients use the `NEXT_PUBLIC_*` Supabase URL/key pair through `web/utils/supabase/client.ts`.

### 4.3 Environment Configuration (Secrets Map)
*Updated for v2.0 Dual-Environment Setup*

| Variable Name | Purpose | Target (Where to Set) |
|---------------|---------|-----------------------|
| `NEXT_PUBLIC_SUPABASE_URL_V2` | v2 DB Endpoint | **Github Secrets** (Actions), **Vercel** (Preview) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2` | v2 DB API Key | **Github Secrets** (Actions), **Vercel** (Preview) |
| `SUPABASE_SERVICE_ROLE_KEY_V2` | v2 service role key mapped to `SUPABASE_SERVICE_ROLE_KEY` in the collector workflow | **Github Secrets** (Actions) |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend/server write key used by Python collectors and `/api/report` | **Vercel** (Web), Local `.env`, mapped from `SUPABASE_SERVICE_ROLE_KEY_V2` in Actions |
| `NEXT_PUBLIC_USE_V2_DB` | v2 Switch Flag (`true`) | **Vercel** (Preview), Local `.env` |
| `ENV_TYPE` | Backend Branch Flag (`v2`) | **Github Actions** (`news_collector_v2.yml`) |
| `GEMINI_ENABLED` | Enables Gemini analysis/reporting only when explicitly true | **Github Actions**, **Vercel**, Local `.env` |
| `GEMINI_API_KEY` | Gemini API key, used only when `GEMINI_ENABLED` is true | **Github Actions**, **Vercel**, Local `.env` |
| `APP_PASSCODE` | Login passcode (server-side compare) | **Vercel** (Web), Local `.env` |
| `SESSION_SECRET` | HMAC key for `mp_session` cookie | **Vercel** (Web), Local `.env` |

### 4.4 Web Dashboard (`web/`)
- **Security**: Protected by `proxy.ts` (Cookie-based Auth). The
  `mp_session` cookie also gates all `/api/*` routes.
- **Visualization**: Reads directly from Supabase `articles` table.
- **`/api/report`**: Accepts only `{ articleId }` in the request body
  (schema in `web/lib/validation/report.ts`). The server then loads
  `title`, `content`, and `agency` from Supabase by id — clients cannot
  inject prompt content. The Gemini prompt is built by
  `buildReportPrompt()` in `web/lib/prompts/report.ts`, and the model id
  is taken from `GEMINI_REPORT_MODEL`. When `GEMINI_ENABLED` is not
  explicitly true, the route returns `503` before Supabase lookup or
  Gemini SDK construction.

### 4.5 Authentication
프론트엔드 인증은 서명된 `mp_session` HMAC 쿠키 기반이다. 사용자가 입력한
passcode는 `/api/auth/login` route 에서 서버측 `APP_PASSCODE` 환경변수와
비교되며, 일치하면 `SESSION_SECRET` 으로 서명된 세션 쿠키가 발급된다.
쿠키 발급/검증 로직은 `web/lib/auth.ts` 에 있고, 보호 대상 route는
`proxy.ts` 가 동일 헬퍼를 사용해 검사한다.

### 4.6 Schema status
현재 애플리케이션 코드와 `db/schema.sql` / `scripts/v2_schema_setup.sql`
사이에 불일치가 있을 수 있다. live DB 기준으로 검증한 뒤 적용하라.

### 4.7 Pipeline dependency injection (testability)
`Pipeline.__init__(config_path, *, analyzer=None, notifier=None, db=None, scraper=None)`.
None일 때 내부 헬퍼로 기본 구성하고, 단위 테스트는 fake를 주입해 외부 I/O 없이
오케스트레이션 흐름을 검증한다. 프로덕션 호출 경로(`src/main.py`)는 None만
넘기므로 동작이 동일하다.
