# Vigil — Judgment Intelligence Monitor

## Project Specification v2.0

> **Client**: Trilegal (internal tool)
> **Purpose**: Real-time monitoring of Supreme Court and High Court judgments by entity, topic, or statutory reference. Delivers alerts when relevant judgments are published.
>
> **Audience**: This document is a complete build specification for Claude Code. Follow it sequentially. Do not skip sections. Ask clarifying questions if anything is ambiguous — this is a high-stakes tool for a Legal 500 firm where missed judgments have real consequences.

---

## Naming Decision

### Recommended: **Vigil**

"Vigil" means "a period of keeping awake during the time usually spent asleep, especially to keep watch." It's Latin-rooted, one word, and carries the exact right connotation — watchfulness, diligence, alertness. It sounds premium and appropriate for a top-tier law firm without being pretentious.



---

## Table of Contents

1. [Architecture Decisions](#1-architecture-decisions)
2. [Technology Stack](#2-technology-stack)
3. [Data Source: Indian Kanoon API](#3-data-source-indian-kanoon-api)
4. [Database Schema (Supabase)](#4-database-schema-supabase)
5. [Backend: Python Polling Worker](#5-backend-python-polling-worker)
6. [Frontend: Next.js Dashboard](#6-frontend-nextjs-dashboard)
7. [Alert & Notification System](#7-alert--notification-system)
8. [Error Handling & Reliability](#8-error-handling--reliability)
9. [Configuration & Environment](#9-configuration--environment)
10. [Project Structure](#10-project-structure)
11. [Testing Strategy](#11-testing-strategy)
12. [Deployment](#12-deployment)
13. [Build Order](#13-build-order)
14. [Future Considerations](#14-future-considerations)

---

## 1. Architecture Decisions

### Why Supabase — Honest Assessment

**Yes, Supabase is a good choice for this project.** But not as a full replacement for the backend — as a **database + auth + real-time layer** paired with a separate Python polling worker. Here's the careful reasoning:

#### What Supabase gives us (and why it matters for Trilegal):

| Feature | Why It Matters |
|---------|---------------|
| **PostgreSQL underneath** | Same schema, full SQL power, pg_trgm, JSONB. No compromises. |
| **Auto-generated REST API (PostgREST)** | The Next.js frontend can read/write watches, judgments, alerts directly via Supabase client — **zero API boilerplate**. No need to write CRUD endpoints manually. |
| **Real-time subscriptions** | When a new judgment match is found, the dashboard updates **live** without refresh. Impressive in demos. |
| **Row Level Security (RLS)** | When Trilegal wants multi-user later (partners vs associates), RLS handles permissions at the database level. |
| **Built-in Auth** | Not needed for v1 (internal tool), but ready for v2 when different team members need separate watchlists. |
| **pg_cron** | Triggers the polling worker on schedule — no external cron needed. |
| **Supabase Dashboard** | Free admin panel for direct DB inspection. Useful for debugging. |
| **Hosted option** | Zero DevOps for v1. Judgment metadata is public data anyway (from Indian Kanoon), so no data sensitivity concern. |

#### What Supabase does NOT solve (and what we need separately):

| Limitation | Our Solution |
|-----------|-------------|
| **Edge Functions are Deno/TypeScript** | The IK API client has an official Python library. Query construction, rate limiting, retry logic — all better in Python. We keep a **separate Python worker**. |
| **Edge Functions have 10min timeout** | Polling 50+ watches with rate limiting could exceed this. Python worker has no timeout. |
| **No built-in email/Slack dispatch** | We handle notifications in the Python worker. |
| **Complex business logic doesn't belong in pg functions** | Query building, deduplication, match scoring — these go in the Python worker, not in SQL. |

#### Architecture: Supabase + Python Worker + Next.js

```
┌──────────────────────────────────────────────────────────────────────┐
│                            Vigil                                     │
│                                                                      │
│  ┌────────────────────┐        ┌──────────────────────────────────┐  │
│  │  Next.js Frontend  │        │  Python Polling Worker           │  │
│  │  (shadcn/ui)       │        │  (Scheduled via pg_cron          │  │
│  │                    │        │   or APScheduler standalone)     │  │
│  │  • Dashboard       │        │                                  │  │
│  │  • Watch Manager   │        │  • IK API Client                │  │
│  │  • Judgment Browser│        │  • Query Builder                │  │
│  │  • Alert History   │        │  • Matcher/Dedup                │  │
│  │  • Settings        │        │  • Notifier (Email + Slack)     │  │
│  └────────┬───────────┘        └──────────┬───────────────────────┘  │
│           │                               │                          │
│           │  Supabase JS Client           │  Supabase Python Client  │
│           │  (reads, writes, real-time)    │  (reads, writes)         │
│           │                               │                          │
│           ▼                               ▼                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Supabase (Cloud or Self-Hosted)            │    │
│  │                                                              │    │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │    │
│  │  │PostgreSQL│  │ PostgREST │  │ Real-time │  │  pg_cron  │  │    │
│  │  │ Database │  │  REST API │  │  Engine   │  │ Scheduler │  │    │
│  │  └──────────┘  └───────────┘  └──────────┘  └───────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│                               ▼                                      │
│                    ┌──────────────────┐                               │
│                    │  Indian Kanoon   │                               │
│                    │  API             │                               │
│                    └──────────────────┘                               │
└──────────────────────────────────────────────────────────────────────┘
```

### Why NOT a Monolith FastAPI + Jinja2

The original v1 spec used FastAPI + Jinja2 (server-side rendered). That's simpler but:

1. **For Trilegal, UI quality matters.** Jinja2 + PicoCSS will look like an intern's side project. Next.js + shadcn/ui looks like a Bloomberg Terminal or Notion — clean, polished, professional.
2. **Real-time updates** require WebSocket plumbing in FastAPI. Supabase gives this for free.
3. **CRUD endpoints** are boilerplate. Supabase auto-generates them from the schema. That's hours of code we don't write.
4. **When they inevitably ask for auth** (different partners, different watchlists), Supabase Auth is ready.

The tradeoff is more moving parts (Supabase + Next.js + Python worker vs. just FastAPI). But for a firm like Trilegal, the quality bar justifies it.

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Database** | Supabase (PostgreSQL 15) | Auto-REST, real-time, auth-ready, pg_cron for scheduling |
| **Frontend** | Next.js 14 (App Router) + TypeScript | Server components, great DX, SSR for fast loads |
| **UI Components** | shadcn/ui + Radix UI + Tailwind CSS | Premium, accessible, dark mode, command palette — looks like a $100K SaaS product |
| **Data Viz** | Tremor (by Tremor Labs) | Beautiful charts and KPI cards designed for dashboards. Built on Tailwind. |
| **Tables** | TanStack Table + shadcn/ui DataTable | Sorting, filtering, pagination, column visibility — the gold standard |
| **Polling Worker** | Python 3.11+ | IK API official client is Python. Complex logic (query building, retries, dedup) is easier in Python. |
| **IK API Client** | httpx (async) | Timeout control, retry logic, async-native |
| **Notifications** | aiosmtplib + slack_sdk | Email and Slack from the Python worker |
| **Scheduler** | APScheduler (in Python worker) | Runs in-process, simpler than pg_cron → Edge Function → HTTP → Python |
| **Icons** | Lucide React | Clean, consistent, used by shadcn/ui |
| **Date Handling** | date-fns (frontend), python-dateutil (backend) | Timezone-aware IST display |

### Why NOT These Alternatives

| Rejected | Reason |
|----------|--------|
| **Jinja2 + PicoCSS** | Not acceptable quality for Trilegal. Looks like a hackathon project. |
| **Supabase Edge Functions for polling** | Deno/TypeScript only. IK API has Python client. Polling logic is complex — better in Python. 10min timeout risk. |
| **pg_cron → HTTP call to Python** | Adds network dependency. If the Python worker is down, pg_cron silently fails. APScheduler in-process is more reliable. |
| **Prisma** | Supabase client is sufficient for frontend reads/writes. Prisma adds unnecessary ORM layer. |
| **tRPC** | Overkill. We don't need end-to-end typesafety between frontend and a separate Python backend. Supabase client handles the frontend-to-DB layer. |
| **Material UI / Ant Design** | Heavier bundles, harder to customize, less modern feel than shadcn/ui. MUI looks "enterprise software" in the bad way. |
| **Recharts** | Tremor is purpose-built for dashboards and integrates better with Tailwind. |

---

## 3. Data Source: Indian Kanoon API

**(Unchanged from v1 — this is the critical data layer)**

### API Reference

- **Base URL**: `https://api.indiankanoon.org`
- **Authentication**: Token-based — `Authorization: Token <API_TOKEN>`
- **Response format**: JSON (set `Accept: application/json` header)
- **Official Python client**: https://github.com/sushant354/IKAPI
- **Pricing**: Prepaid. ₹500 free on signup. Non-commercial use gets ₹10,000/month free (requires verification).

### Endpoints We Use

#### 1. Search (`GET /search/`)

```
GET https://api.indiankanoon.org/search/?formInput=<query>&pagenum=<page>
```

**Key parameters in `formInput`**:

| Parameter | Usage | Example |
|-----------|-------|---------|
| Plain text | Full-text search | `"Amazon Web Services"` (quotes for exact phrase) |
| `doctypes:` | Filter by court | `doctypes:supremecourt,delhi,bombay` |
| `fromdate:` | Min date (DD-MM-YYYY) | `fromdate:15-02-2026` |
| `todate:` | Max date (DD-MM-YYYY) | `todate:18-02-2026` |
| `title:` | Search in title only | `title:Amazon` |
| `ANDD` / `ORR` / `NOTT` | Boolean operators (case-sensitive, space-padded) | `"DTAA" ANDD "Mauritius"` |

**Response fields per doc**:

| Field | Type | Description |
|-------|------|-------------|
| `tid` | int | Indian Kanoon document ID (unique, stable) |
| `title` | string | Case title |
| `docsource` | string | Court name |
| `headline` | string | Snippet with highlighted match |
| `publishdate` | string | Date of judgment |
| `numcites` | int | Citation count |
| `docsize` | int | Document size in characters |

#### 2. Document Metadata (`GET /docmeta/<docid>/`)

For enriching matched judgments with bench composition, acts cited, AI tags.

### API Cost Rules (CRITICAL)

1. **Always use `fromdate`** — set to last successful poll timestamp. Never do open-ended searches.
2. **Page 0 is usually sufficient** — only fetch page 1+ if `found` > 10.
3. **Cache document IDs** — deduplicate before creating alerts.
4. **Rate limit: 1 request per 2 seconds** — be respectful to the API.
5. **Never poll more frequently than every 2 hours** — judgments are published in batches.
6. **Log every API call** — track spend against prepaid balance.

### Query Construction

**Entity watch** (e.g., "Amazon Web Services"):
```
"Amazon Web Services" doctypes:supremecourt,judgments fromdate:15-02-2026
```

**Topic watch** (e.g., "India Mauritius DTAA"):
```
"India Mauritius" ANDD "DTAA" doctypes:supremecourt,judgments fromdate:15-02-2026
```

**Act watch** (e.g., "Information Technology Act"):
```
"Information Technology Act" doctypes:supremecourt,judgments fromdate:15-02-2026
```

Note: `judgments` is a documented IK aggregator covering SC + HC + District Courts. Let users also configure specific court codes if needed.

---

## 4. Database Schema (Supabase)

Create these tables via the Supabase SQL editor or through migrations. All timestamps UTC.

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- WATCHES: What the user wants to monitor
-- ============================================================
CREATE TABLE watches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    watch_type          VARCHAR(20) NOT NULL
                        CHECK (watch_type IN ('entity', 'topic', 'act')),
    query_terms         TEXT NOT NULL,
    query_template      TEXT,
    court_filter        TEXT[] DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    polling_interval_minutes INTEGER NOT NULL DEFAULT 120
                        CHECK (polling_interval_minutes >= 120),
    last_polled_at      TIMESTAMPTZ,
    last_poll_result_count INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- JUDGMENTS: Cached metadata of matched judgments
-- ============================================================
CREATE TABLE judgments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ik_doc_id       BIGINT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    court           VARCHAR(255),
    judgment_date   DATE,
    headline        TEXT,
    doc_size        INTEGER,
    num_cites       INTEGER DEFAULT 0,
    ik_url          TEXT GENERATED ALWAYS AS (
                        'https://indiankanoon.org/doc/' || ik_doc_id || '/'
                    ) STORED,
    metadata_json   JSONB DEFAULT '{}',
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_judgments_ik_doc_id ON judgments(ik_doc_id);
CREATE INDEX idx_judgments_court ON judgments(court);
CREATE INDEX idx_judgments_judgment_date ON judgments(judgment_date);
CREATE INDEX idx_judgments_title_trgm ON judgments USING gin (title gin_trgm_ops);

-- ============================================================
-- WATCH_MATCHES: Which watches matched which judgments
-- ============================================================
CREATE TABLE watch_matches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_id        UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    judgment_id     UUID NOT NULL REFERENCES judgments(id) ON DELETE CASCADE,
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relevance_score FLOAT,
    snippet         TEXT,
    is_notified     BOOLEAN NOT NULL DEFAULT FALSE,
    notified_at     TIMESTAMPTZ,

    CONSTRAINT unique_watch_judgment UNIQUE (watch_id, judgment_id)
);

CREATE INDEX idx_watch_matches_watch_id ON watch_matches(watch_id);
CREATE INDEX idx_watch_matches_pending ON watch_matches(is_notified) WHERE is_notified = FALSE;

-- ============================================================
-- NOTIFICATION_LOG: Record of every alert sent
-- ============================================================
CREATE TABLE notification_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_match_id  UUID REFERENCES watch_matches(id),
    channel         VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'slack')),
    recipient       TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed', 'retrying')),
    error_message   TEXT,
    sent_at         TIMESTAMPTZ,
    retry_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- API_CALL_LOG: Track IK API usage for cost monitoring
-- ============================================================
CREATE TABLE api_call_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    endpoint        VARCHAR(50) NOT NULL,
    request_url     TEXT NOT NULL,
    watch_id        UUID REFERENCES watches(id),
    http_status     INTEGER,
    result_count    INTEGER,
    response_time_ms INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_call_log_created ON api_call_log(created_at);

-- ============================================================
-- APP_SETTINGS: Key-value config
-- ============================================================
CREATE TABLE app_settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           TEXT NOT NULL,
    description     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO app_settings (key, value, description) VALUES
    ('notification_email_enabled', 'true', 'Enable email notifications'),
    ('notification_slack_enabled', 'false', 'Enable Slack notifications'),
    ('notification_email_recipients', '', 'Comma-separated email addresses'),
    ('notification_slack_webhook_url', '', 'Slack incoming webhook URL'),
    ('default_court_filter', '', 'Default court codes for new watches'),
    ('global_polling_enabled', 'true', 'Master switch for polling'),
    ('daily_digest_enabled', 'true', 'Send daily digest'),
    ('daily_digest_time', '09:00', 'Digest time (HH:MM IST)');

-- ============================================================
-- ROW LEVEL SECURITY (Prepare for multi-user v2)
-- ============================================================
-- For v1, disable RLS (internal tool, single-team access).
-- When multi-user is needed, enable RLS and add policies:
--
-- ALTER TABLE watches ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Users can view their own watches"
--     ON watches FOR SELECT USING (auth.uid() = user_id);

-- ============================================================
-- REAL-TIME: Enable for live dashboard updates
-- ============================================================
-- In Supabase Dashboard → Database → Replication:
-- Enable real-time for: watches, judgments, watch_matches

-- ============================================================
-- UPDATED_AT TRIGGER: Auto-update timestamp
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER watches_updated_at
    BEFORE UPDATE ON watches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### Schema Design Rationale

1. **Separate `judgments` and `watch_matches`**: A judgment may match 5 different watches. Normalizing prevents duplicate storage and enables "this judgment matched 3 of your watches" in the UI.
2. **`ik_doc_id` as BIGINT UNIQUE**: The deduplication key. `INSERT ... ON CONFLICT DO NOTHING`.
3. **`is_notified` on `watch_matches`**: Decouples matching from notification. If Slack is down, the match is still recorded.
4. **Generated column `ik_url`**: Always-correct link. Zero URL construction bugs.
5. **`api_call_log`**: Essential for tracking spend against IK prepaid balance.
6. **Real-time enabled on key tables**: Supabase pushes changes to the Next.js frontend instantly.

---

## 5. Backend: Python Polling Worker

This is a **standalone Python process** that runs alongside the Next.js frontend. It handles all Indian Kanoon API interaction, business logic, and notifications.

### Project Structure

```
vigil-worker/
├── vigil/
│   ├── __init__.py
│   ├── config.py               # Settings from environment
│   ├── supabase_client.py      # Supabase Python client setup
│   ├── ik_client.py            # Indian Kanoon API client (async httpx)
│   ├── query_builder.py        # Construct formInput from watch config
│   ├── matcher.py              # Deduplication & match recording
│   ├── polling.py              # Polling engine (APScheduler)
│   ├── notifier.py             # Email + Slack dispatch
│   └── main.py                 # Entry point: start scheduler + run
│
├── tests/
│   ├── test_query_builder.py
│   ├── test_matcher.py
│   ├── test_ik_client.py
│   └── test_notifier.py
│
├── pyproject.toml
├── Dockerfile
├── .env.example
└── README.md
```

### Module Specifications

#### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    supabase_url: str                           # e.g., https://xxxx.supabase.co
    supabase_service_role_key: str              # Service role key (bypasses RLS)

    # Indian Kanoon API
    ik_api_token: str                           # REQUIRED
    ik_api_base_url: str = "https://api.indiankanoon.org"
    ik_api_timeout_seconds: int = 30
    ik_api_max_retries: int = 3

    # Notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    slack_webhook_url: str = ""

    # Polling
    polling_enabled: bool = True

    # App
    timezone: str = "Asia/Kolkata"

    class Config:
        env_file = ".env"
        env_prefix = "VIGIL_"
```

#### `supabase_client.py`

```python
"""
Supabase client for the Python worker.

Uses the SERVICE_ROLE key (not anon key) because:
1. This is a backend worker, not a browser client.
2. Service role bypasses RLS — needed for writing matches from the polling engine.
3. Never expose the service role key to the frontend.

The Next.js frontend uses the anon key with RLS policies.
"""
from supabase import create_client
from vigil.config import settings

supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
```

#### `ik_client.py`

```python
"""
Indian Kanoon API Client.

DESIGN PRINCIPLES:
1. Every API call is logged to api_call_log via Supabase.
2. All calls have timeouts (30s default).
3. Retries with exponential backoff on 5xx and network errors.
4. Never retry on 4xx — these are bugs, not transient errors.
5. Rate limiting: max 1 request per 2 seconds (asyncio.Semaphore + sleep).
6. All methods are async.
"""

# Methods:
async def search(form_input: str, page_num: int = 0) -> dict: ...
async def get_doc_meta(doc_id: int) -> dict: ...

# Errors:
class IKAPIError(Exception): ...
class IKAPIAuthError(IKAPIError): ...       # 403 — pause all polling
class IKAPITimeoutError(IKAPIError): ...    # Timeout after retries
class IKAPIRateLimitError(IKAPIError): ...  # 429 — back off
```

#### `query_builder.py`

```python
"""
Constructs Indian Kanoon formInput strings.

RULES:
1. Entity names ALWAYS in quotes for exact phrase matching.
2. Multi-word topic terms in quotes. Single words left bare.
3. Court filter appended as doctypes: parameter.
4. fromdate: ALWAYS included — set to last_polled_at or creation date.
5. Date format: DD-MM-YYYY (Indian Kanoon's expected format).
"""

def build_query(
    watch_type: str,
    query_terms: str,
    court_filter: list[str],
    from_date: date,
    to_date: date | None = None
) -> str: ...
```

#### `polling.py`

```python
"""
Polling engine.

FLOW PER CYCLE:
1. Fetch active watches from Supabase where interval has elapsed.
2. For each watch:
   a. Build query → call IK search → process results via matcher.
   b. Update last_polled_at.
3. Trigger notification dispatch for pending matches.

ERROR HANDLING:
- Single watch failure → log and continue. Never halt the cycle.
- IK API 403 → PAUSE ALL polling. Admin alert.
- IK API 5xx/timeout → exponential backoff for that watch.

SCHEDULING:
- APScheduler AsyncIOScheduler
- Main cycle: every 30 minutes (only polls watches whose interval has elapsed)
- Notification dispatch: every 10 minutes
- Daily digest: 9:00 AM IST
"""
```

#### `matcher.py`

```python
"""
Deduplication and match recording.

CRITICAL: This module prevents missed judgments AND duplicate alerts.

LOGIC:
1. For each search result doc:
   - Check if ik_doc_id exists in judgments table.
   - If not, INSERT (upsert with ON CONFLICT DO NOTHING).
   - Check if (watch_id, judgment_id) exists in watch_matches.
   - If not, INSERT with is_notified=FALSE.
2. Return only NEWLY created matches for notification.
"""
```

#### `notifier.py`

```python
"""
Notification dispatch.

RULES:
1. Batch by watch — one email per watch, not per judgment.
2. On success: set is_notified=TRUE.
3. On failure: log error, DO NOT set is_notified. Retry next cycle (max 3).
4. Daily digest: summary of all matches from past 24h.

EMAIL SUBJECT: "[Vigil] {watch_name}: {count} new judgment(s)"
SLACK: Block Kit formatted with linked titles, court, date.
"""
```

### Python Dependencies (`pyproject.toml`)

```toml
[project]
name = "vigil-worker"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "supabase>=2.0.0",
    "httpx>=0.27.0",
    "apscheduler>=3.10.0",
    "pydantic-settings>=2.1.0",
    "slack-sdk>=3.27.0",
    "aiosmtplib>=3.0.0",
    "python-dateutil>=2.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
]
```

---

## 6. Frontend: Next.js Dashboard

### Design Direction

**Aesthetic**: Refined legal-tech. Think Bloomberg Terminal meets Linear. Dark mode default (lawyers work late). Clean typography. Dense but not cluttered. Data-rich without being overwhelming.

**Design tokens**:
- **Primary**: Deep navy/slate (`#0F172A` background, `#F8FAFC` text in dark mode)
- **Accent**: A sophisticated blue (`#3B82F6`) or warm amber (`#F59E0B`) for alerts
- **Font**: `"Inter"` for body (clean, readable, great for data tables), `"Instrument Serif"` or `"Newsreader"` for headings (adds legal gravitas without being stuffy)
- **Dark mode default** with light mode toggle
- **Spacing**: Generous but not wasteful. 16px base grid.

**Key UI patterns**:
- **Sidebar navigation** (collapsible) — not top navbar. Dashboards need vertical space.
- **Command palette** (Cmd+K) — shadcn/ui provides this. Quick-jump to any watch or judgment.
- **Toast notifications** — for real-time updates ("New judgment matched: AWS vs DCIT")
- **Data tables with TanStack** — sortable, filterable, column toggle, pagination
- **KPI cards** — Tremor AreaChart for trends, number cards for key metrics

### Project Structure

```
vigil-web/
├── app/
│   ├── layout.tsx                  # Root layout with sidebar, providers
│   ├── page.tsx                    # Dashboard (home)
│   ├── watches/
│   │   ├── page.tsx                # All watches list
│   │   ├── new/page.tsx            # Create new watch
│   │   └── [id]/page.tsx           # Watch detail + edit
│   ├── judgments/
│   │   └── page.tsx                # Browse all matched judgments
│   ├── alerts/
│   │   └── page.tsx                # Notification history
│   └── settings/
│       └── page.tsx                # App configuration
│
├── components/
│   ├── ui/                         # shadcn/ui components (auto-installed)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── data-table.tsx
│   │   ├── dialog.tsx
│   │   ├── command.tsx             # Command palette (Cmd+K)
│   │   ├── badge.tsx
│   │   ├── toast.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── sidebar.tsx             # Main sidebar navigation
│   │   ├── header.tsx              # Page header with breadcrumbs
│   │   └── theme-toggle.tsx        # Dark/light mode switch
│   ├── dashboard/
│   │   ├── stats-cards.tsx         # KPI cards (total watches, matches today, etc.)
│   │   ├── recent-matches.tsx      # Latest matched judgments
│   │   ├── api-usage-chart.tsx     # API credit usage over time
│   │   └── system-health.tsx       # Last poll time, failed watches
│   ├── watches/
│   │   ├── watch-form.tsx          # Create/edit watch form
│   │   ├── watch-card.tsx          # Watch summary card
│   │   ├── court-selector.tsx      # Multi-select for court filter
│   │   └── poll-now-button.tsx     # Trigger immediate poll
│   ├── judgments/
│   │   ├── judgment-table.tsx      # TanStack Table with all matched judgments
│   │   ├── judgment-row.tsx        # Single judgment display
│   │   └── court-badge.tsx         # Color-coded court indicator
│   └── alerts/
│       └── notification-table.tsx  # Alert history with status badges
│
├── lib/
│   ├── supabase/
│   │   ├── client.ts               # Browser Supabase client (anon key)
│   │   ├── server.ts               # Server Supabase client
│   │   └── types.ts                # Generated TypeScript types from schema
│   ├── hooks/
│   │   ├── use-watches.ts          # React Query hook for watches
│   │   ├── use-judgments.ts        # React Query hook for judgments
│   │   └── use-realtime.ts         # Supabase real-time subscription hook
│   └── utils.ts                    # Date formatting (IST), helpers
│
├── public/
│   └── vigil-logo.svg
│
├── tailwind.config.ts
├── next.config.js
├── package.json
├── tsconfig.json
└── .env.local.example
```

### Page Specifications

#### Dashboard (`/`)

```
┌─────────────────────────────────────────────────────────────┐
│  ≡ Vigil                                          🌙 ⌘K    │
├──────┬──────────────────────────────────────────────────────│
│      │                                                      │
│  📊  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│ Dash │  │ 12       │ │ 7        │ │ 43       │ │ ₹3,200 │ │
│      │  │ Active   │ │ New today│ │ This week│ │ API    │ │
│  👁  │  │ Watches  │ │ Matches  │ │ Matches  │ │ Balance│ │
│Watch │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│      │                                                      │
│  ⚖️  │  Recent Matches                              See All│
│ Judg │  ┌──────────────────────────────────────────────────┐│
│      │  │ AWS vs DCIT · Delhi HC · 17 Feb 2026     🔗     ││
│  🔔  │  │ Reliance v SEBI · SC · 16 Feb 2026       🔗     ││
│Alert │  │ DPDP Act compliance · Bombay HC · 15 Feb  🔗     ││
│      │  └──────────────────────────────────────────────────┘│
│  ⚙️  │                                                      │
│ Set  │  API Usage (Last 30 Days)                            │
│      │  ┌──────────────────────────────────────────────────┐│
│      │  │  ▁▂▃▅▆█▇▅▃▂▁▂▃▄▅▆▇█▇▅▄▃▂▁▂▃▅▇█  (Tremor)     ││
│      │  └──────────────────────────────────────────────────┘│
│      │                                                      │
│      │  System Health                                       │
│      │  ● Last poll: 2 minutes ago                         │
│      │  ● All watches healthy                              │
│      │  ● Next poll: in 28 minutes                         │
└──────┴──────────────────────────────────────────────────────┘
```

**Components used**: Tremor `Card`, `AreaChart`, `BarList`. shadcn `Badge`, `Table`.

#### Watches (`/watches`)

- **Data table**: Name, Type (badge: entity/topic/act), Status (active/paused), Last Polled, Total Matches, Actions
- **"New Watch" button** → dialog form (not separate page) with:
  - Name (text)
  - Type (radio: Entity / Topic / Act)
  - Query Terms (text, with placeholder examples per type)
  - Court Filter (multi-select combobox with all SC + HC options)
  - Polling Interval (dropdown: 2h, 4h, 6h, 12h, 24h)
- **Row actions**: Edit, Pause/Resume, "Poll Now" (triggers immediate poll), Delete (with confirmation)

#### Watch Detail (`/watches/[id]`)

- Watch config summary at top
- **Matched Judgments tab**: Table of all judgments matched to this watch (newest first)
- **Poll History tab**: API call log entries for this watch
- **Edit form** (inline, same page)

#### Judgments (`/judgments`)

- **Master table** of all cached judgments across all watches
- Columns: Title (linked to IK), Court (color-coded badge), Date, Matched Watches (count + list), Citation Count
- **Filters**: Court dropdown, date range picker, text search
- **Click row** → expand to show headline/snippet + link to Indian Kanoon

#### Alerts (`/alerts`)

- Notification log table: Date, Watch Name, Channel (email/slack badge), Status (sent/failed/retrying), Recipient
- Filters by channel, status, date range

#### Settings (`/settings`)

- **Notifications section**: Enable/disable email, Slack. Configure recipients, webhook URL.
- **Polling section**: Global on/off switch. Default court filter.
- **Daily Digest section**: Enable/disable. Configure time.
- **Danger Zone**: Clear all data, reset settings.

### Frontend Dependencies (`package.json`)

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@supabase/supabase-js": "^2.45.0",
    "@supabase/ssr": "^0.5.0",
    "@tanstack/react-table": "^8.20.0",
    "@tanstack/react-query": "^5.60.0",
    "tailwindcss": "^3.4.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.5.0",
    "lucide-react": "^0.400.0",
    "@tremor/react": "^3.18.0",
    "date-fns": "^4.1.0",
    "date-fns-tz": "^3.2.0",
    "sonner": "^1.5.0",
    "cmdk": "^1.0.0",
    "nuqs": "^2.0.0",
    "zod": "^3.23.0",
    "react-hook-form": "^7.53.0",
    "@hookform/resolvers": "^3.9.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@types/react": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

### Real-time Integration

```typescript
// lib/hooks/use-realtime.ts
import { useEffect } from 'react'
import { supabase } from '@/lib/supabase/client'

/**
 * Subscribe to new watch matches in real-time.
 * When the Python worker inserts a new match, the dashboard
 * updates instantly — no page refresh needed.
 */
export function useRealtimeMatches(onNewMatch: (match: WatchMatch) => void) {
  useEffect(() => {
    const channel = supabase
      .channel('watch_matches_changes')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'watch_matches' },
        (payload) => {
          onNewMatch(payload.new as WatchMatch)
          // Also show a toast notification
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [onNewMatch])
}
```

### "Poll Now" Implementation

When a user clicks "Poll Now" on a watch:

1. Frontend inserts a row into a `poll_requests` table (simple queue):
   ```sql
   CREATE TABLE poll_requests (
       id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       watch_id    UUID NOT NULL REFERENCES watches(id),
       status      VARCHAR(20) DEFAULT 'pending'
                   CHECK (status IN ('pending', 'processing', 'done', 'failed')),
       created_at  TIMESTAMPTZ DEFAULT NOW()
   );
   ```
2. Python worker checks this table every 30 seconds (separate lightweight job).
3. When a pending request is found: process it, update status to 'done'.
4. Frontend subscribes to real-time changes on `poll_requests` — shows spinner while processing, then refreshes results.

This is cleaner than a direct HTTP call to the Python worker (which would require exposing an endpoint).

---

## 7. Alert & Notification System

### Email Template

```
Subject: [Vigil] AWS Judgments: 3 new judgment(s) found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Vigil — Judgment Alert
  Watch: AWS Judgments
  3 new judgment(s) matched

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Amazon Web Services Inc. vs Commissioner of Income Tax
     Court:  Delhi High Court
     Date:   17 Feb 2026
     Link:   https://indiankanoon.org/doc/12345678/

  2. M/s AWS India Pvt Ltd vs Union of India
     Court:  Supreme Court of India
     Date:   16 Feb 2026
     Link:   https://indiankanoon.org/doc/23456789/

  3. In Re: Cloud Services Data Localisation
     Court:  Karnataka High Court
     Date:   15 Feb 2026
     Link:   https://indiankanoon.org/doc/34567890/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Vigil · Trilegal Internal Tool
```

### Slack Message (Block Kit)

```json
{
  "blocks": [
    {
      "type": "header",
      "text": { "type": "plain_text", "text": "⚖️ Vigil: AWS Judgments — 3 new judgment(s)" }
    },
    { "type": "divider" },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*<https://indiankanoon.org/doc/12345678/|Amazon Web Services Inc. vs Commissioner of Income Tax>*\n📍 Delhi High Court · 📅 17 Feb 2026"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*<https://indiankanoon.org/doc/23456789/|M/s AWS India Pvt Ltd vs Union of India>*\n📍 Supreme Court · 📅 16 Feb 2026"
      }
    },
    {
      "type": "context",
      "elements": [
        { "type": "mrkdwn", "text": "Vigil · Trilegal Internal" }
      ]
    }
  ]
}
```

---

## 8. Error Handling & Reliability

### Error Matrix

| Error | Severity | Response |
|-------|----------|----------|
| IK API 403 | **CRITICAL** | Pause ALL polling. Admin alert via Slack + email. |
| IK API 429 | HIGH | Exponential backoff. Double interval temporarily. |
| IK API 5xx | MEDIUM | Retry 3x (2s, 4s, 8s). Skip watch on failure. |
| IK API timeout | MEDIUM | Same as 5xx. |
| Unexpected JSON | MEDIUM | Log full response. Skip result. Don't crash. |
| Supabase down | **CRITICAL** | Worker retries on next cycle. |
| SMTP failure | LOW | Log error. Retry next dispatch (max 3). |
| Slack webhook failure | LOW | Same as SMTP. |
| Single watch failure | LOW | Log and continue with other watches. |

### Data Integrity

1. **`ON CONFLICT DO NOTHING`** on all upserts — idempotent by design.
2. **Each watch's results committed atomically** — partial failure doesn't corrupt state.
3. **Never delete judgments** — watch deletion cascades to matches only.
4. **All times in UTC** in database, displayed in IST on frontend.

---

## 9. Configuration & Environment

### Python Worker `.env`

```bash
# Supabase
VIGIL_SUPABASE_URL=https://your-project.supabase.co
VIGIL_SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...

# Indian Kanoon API
VIGIL_IK_API_TOKEN=your_ik_api_token

# Email (optional)
VIGIL_SMTP_HOST=smtp.gmail.com
VIGIL_SMTP_PORT=587
VIGIL_SMTP_USERNAME=vigil@trilegal.com
VIGIL_SMTP_PASSWORD=app_password
VIGIL_SMTP_FROM_EMAIL=vigil@trilegal.com
VIGIL_SMTP_USE_TLS=true

# Slack (optional)
VIGIL_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Polling
VIGIL_POLLING_ENABLED=true
VIGIL_TIMEZONE=Asia/Kolkata
```

### Next.js `.env.local`

```bash
# Supabase (anon key — safe for browser)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...

# App
NEXT_PUBLIC_APP_NAME=Vigil
NEXT_PUBLIC_TIMEZONE=Asia/Kolkata
```

---

## 10. Project Structure (Monorepo)

```
vigil/
├── apps/
│   ├── web/                        # Next.js frontend
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── public/
│   │   ├── next.config.js
│   │   ├── tailwind.config.ts
│   │   ├── package.json
│   │   └── .env.local.example
│   │
│   └── worker/                     # Python polling worker
│       ├── vigil/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── supabase_client.py
│       │   ├── ik_client.py
│       │   ├── query_builder.py
│       │   ├── matcher.py
│       │   ├── polling.py
│       │   └── notifier.py
│       ├── tests/
│       ├── pyproject.toml
│       ├── Dockerfile
│       └── .env.example
│
├── supabase/
│   ├── migrations/
│   │   └── 001_initial_schema.sql  # Full schema from Section 4
│   └── config.toml
│
├── docker-compose.yml              # For local development
├── README.md
└── .gitignore
```

### docker-compose.yml (Development)

```yaml
version: "3.8"

services:
  worker:
    build: ./apps/worker
    env_file: ./apps/worker/.env
    restart: unless-stopped
    depends_on:
      - web

  web:
    build: ./apps/web
    ports:
      - "3000:3000"
    env_file: ./apps/web/.env.local
    restart: unless-stopped
```

Note: Supabase runs as a cloud service. No local Supabase container needed for development (use the Supabase project directly). For fully offline development, use `supabase start` (Supabase CLI local stack).

---

## 11. Testing Strategy

### Python Worker Tests (Priority: HIGH)

| Module | Tests |
|--------|-------|
| `query_builder.py` | Entity queries → exact phrase. Topic → ANDD operator. Date → DD-MM-YYYY. Empty court filter → no doctypes. |
| `matcher.py` | New judgment inserted. Duplicate ik_doc_id skipped. New match created. Duplicate match skipped. Only new matches returned. |
| `ik_client.py` | Mock httpx. 200 → JSON. 403 → IKAPIAuthError. 5xx → retry. Timeout → IKAPITimeoutError. |
| `notifier.py` | Email format correct. Slack blocks valid JSON. Failed send logged. Retry count incremented. |

### Frontend Tests (Priority: MEDIUM)

- Component rendering with mock Supabase data
- Form validation (watch creation)
- Real-time subscription handling

### Manual Testing Checklist

- [ ] Create entity watch for "Reliance Industries" → results appear
- [ ] Create topic watch for "DPDP Act" → results appear
- [ ] Pause/resume watch → polling respects state
- [ ] "Poll Now" → immediate results
- [ ] Real-time: match appears in dashboard without refresh
- [ ] Email alert arrives with correct format and links
- [ ] Slack alert posts correctly
- [ ] Dark mode renders correctly across all pages
- [ ] Command palette (Cmd+K) navigates correctly
- [ ] Data table sorting/filtering works
- [ ] After 24h: no duplicates, no missed obvious judgments
- [ ] API call log shows reasonable usage

---

## 12. Deployment

### Option A: Supabase Cloud + Vercel + Railway (Recommended for v1)

| Component | Platform | Cost |
|-----------|----------|------|
| Database + Auth + Real-time | Supabase Cloud (Free → Pro at $25/mo) | $0–25/mo |
| Next.js Frontend | Vercel (Free → Pro) | $0–20/mo |
| Python Worker | Railway ($5/mo) or Render | $5–7/mo |
| **Total** | | **$5–52/mo** |

### Option B: Self-Hosted (Full Control)

| Component | Platform | Notes |
|-----------|----------|-------|
| Everything | Single VPS (Hetzner/DigitalOcean, 2 vCPU, 4GB) | ~$12/mo |
| Supabase | Self-hosted via Docker | Full stack including Studio |
| Next.js | Docker or PM2 | |
| Worker | Docker or systemd | |

### Quick Start

```bash
# 1. Set up Supabase project (cloud.supabase.com)
# 2. Run migrations
supabase db push

# 3. Start frontend
cd apps/web
npm install
npm run dev   # → http://localhost:3000

# 4. Start worker
cd apps/worker
pip install -e ".[dev]"
python -m vigil.main
```

---

## 13. Build Order for Claude Code

**CRITICAL**: Implement in this exact sequence. Verify each step before proceeding.

### Phase 1: Foundation
1. **Monorepo scaffolding** — folder structure, configs, `.gitignore`
2. **Supabase schema** — run SQL from Section 4 via migrations
3. **Python worker skeleton** — config.py, supabase_client.py, main.py

### Phase 2: Core Engine
4. **ik_client.py** — full IK API client with retries, rate limiting, logging
5. **query_builder.py** — all three watch types, date formatting, court filter
6. **matcher.py** — deduplication logic with Supabase upserts
7. **polling.py** — APScheduler integration, full polling cycle

### Phase 3: Notifications
8. **notifier.py** — email + Slack dispatch with batching and retry

### Phase 4: Frontend
9. **Next.js setup** — shadcn/ui init, Tailwind config, Supabase client, layout with sidebar
10. **Dashboard page** — stats cards, recent matches, API usage chart, system health
11. **Watches pages** — list, create (dialog), detail/edit, "Poll Now"
12. **Judgments page** — data table with TanStack, filters, court badges
13. **Alerts page** — notification history table
14. **Settings page** — notification config, polling controls

### Phase 5: Integration
15. **Real-time subscriptions** — live match updates, toast notifications
16. **Poll Now queue** — poll_requests table + worker handling
17. **Command palette** — Cmd+K for quick navigation

### Phase 6: Polish
18. **Dark/light mode** — proper theme toggle with persistence
19. **Loading states** — skeletons for all data-loading components
20. **Error boundaries** — graceful error handling in all pages
21. **Tests** — unit tests for query_builder, matcher, ik_client

---

## 14. Future Considerations

Explicitly **out of scope for v1**, documented for planning:

1. **AI Summarization**: Claude API to generate one-paragraph summaries of matched judgments.
2. **PDF Storage**: Fetch and store original court copies from IK premium.
3. **Tribunal Monitoring**: ITAT, NCLT, NCLAT, SAT, TDSAT — already supported by IK doctypes.
4. **Multi-user Auth**: Enable Supabase Auth + RLS. Per-user watchlists.
5. **kanoon.dev as Secondary Source**: Backup data source with structured case events and insights.
6. **Webhook Alerts**: External systems subscribe to match events.
7. **Historical Backfill**: AWS Open Data SC Judgments dataset (1950–present, CC-BY-4.0).
8. **RSS Feeds**: Per-watch RSS/Atom feeds for feed reader subscribers.
9. **Relevance Scoring**: LLM-based relevance scoring (1–10) for each match.
10. **Duplicate Detection**: pg_trgm similarity matching across different IK doc IDs for same judgment.
11. **Mobile Notifications**: Push notifications via Firebase Cloud Messaging.
12. **Teams Integration**: If Trilegal uses Microsoft Teams, send alerts there too.

---

*Vigil — Judgment Intelligence Monitor*
*Specification v2.0 | 18 February 2026*
*For Trilegal Internal Use*