# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Vigil — Judgment Intelligence Monitor. An internal tool for Trilegal that monitors Supreme Court and High Court judgments in India via the Indian Kanoon API. Supabase project ID: `oqvzksndvjpktpmcxumn` (region: ap-south-1).

## Monorepo Layout

```
apps/web/       # Next.js 16 frontend (App Router, React 19, shadcn/ui, Tailwind v4, Tremor charts)
apps/worker/    # Python 3.11+ async polling worker (APScheduler, httpx, aiosmtplib)
supabase/       # PostgreSQL migrations & config (7 tables, pg_trgm, real-time)
```

Apps are independent — no workspace config. Install deps separately.

## Commands

### Frontend (`apps/web/`)
```bash
npm run dev                  # Dev server on :3000
npm run build                # Production build
npm run lint                 # ESLint
npm run test                 # Vitest (watch mode)
npm run test:run             # Vitest (single run)
npm run test:coverage        # Vitest with coverage
```

### Worker (`apps/worker/`)
```bash
pip install -e ".[dev]"                    # Install with dev deps
python -m vigil.main                       # Run worker
pytest                                     # All tests
pytest tests/test_polling.py -v            # Single test file
pytest tests/test_polling.py::test_name -v # Single test
pytest --cov=vigil                         # Coverage
ruff check vigil/                          # Lint
ruff format vigil/                         # Format
```

## Architecture

**Data flow:** Indian Kanoon API → Python Worker (IKClient → QueryBuilder → Matcher → Notifier) → Supabase → Next.js Frontend (real-time subscriptions)

### Database (7 tables)
- `watches` — what to monitor (entity/topic/act type, court filters, interval)
- `judgments` — cached judgment metadata, deduped by `ik_doc_id`
- `watch_matches` — join table with unique constraint `(watch_id, judgment_id)`
- `notification_log` — audit trail of sent alerts
- `api_call_log` — IK API usage tracking
- `app_settings` — key-value global config
- `poll_requests` — queue for "Poll Now" feature

Real-time enabled on: `watches`, `watch_matches`, `poll_requests`.

### Worker modules (each single-responsibility)
- `config.py` — Pydantic Settings, env vars with `VIGIL_` prefix
- `ik_client.py` — async IK API client with rate limiting (1 req/2s semaphore), retries, error classes
- `query_builder.py` — builds IK `formInput` strings from watch config
- `matcher.py` — upserts judgments, creates watch_matches with `ON CONFLICT DO NOTHING`
- `polling.py` — APScheduler cycles (30min main, 10min notifications, 30sec poll requests)
- `notifier.py` — email (aiosmtplib) + Slack (httpx Block Kit), batches per watch

### Frontend structure
- `app/` — App Router pages (dashboard, watches, judgments, alerts, settings)
- `components/` — feature-based folders (dashboard/, watches/, judgments/, alerts/, layout/)
- `components/ui/` — shadcn/ui primitives
- `lib/supabase/` — browser + server clients, generated types
- `lib/hooks/` — React Query hooks + real-time subscriptions

## Key Patterns

### Worker testing
- `asyncio_mode = "auto"` in pyproject.toml — no `@pytest.mark.asyncio` needed
- Supabase mocking: chainable `MagicMock` with `side_effect` lists for sequential `.execute()` returns
- Settings patching: must patch both `vigil.config.settings` AND module-level imports (e.g., `vigil.notifier.settings`). The `test_settings` fixture in `conftest.py` handles this.

### Worker error handling hierarchy
- **403 auth error** → pause all polling, alert admin
- **429 rate limit / 5xx** → exponential backoff per watch
- **Single watch failure** → log, skip, continue cycle
- **SMTP/Slack failure** → retry up to 3 times

### Frontend conventions
- Server components by default, `"use client"` only for interactivity
- TanStack React Query for server state, `useMutation` for writes
- react-hook-form + Zod for form validation
- date-fns with IST timezone (`Asia/Kolkata`) — all DB timestamps are UTC
- Sonner for toast notifications, cmdk for Cmd+K navigation

### Database conventions
- All upserts use `ON CONFLICT DO NOTHING` for idempotency
- `ik_url` is a generated column from `ik_doc_id`
- `update_updated_at()` trigger on all tables
- No RLS in v1 (internal single-team tool)

## Environment Variables

**Worker** (`apps/worker/.env`): `VIGIL_SUPABASE_URL`, `VIGIL_SUPABASE_SERVICE_ROLE_KEY`, `VIGIL_IK_API_TOKEN`, `VIGIL_SMTP_*`, `VIGIL_SLACK_WEBHOOK_URL`, `VIGIL_TIMEZONE` (default: `Asia/Kolkata`)

**Frontend** (`apps/web/.env.local`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
