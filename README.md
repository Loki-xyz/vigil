# Vigil — Judgment Intelligence Monitor

Real-time monitoring of Supreme Court and High Court judgments by entity, topic, or statutory reference. Delivers alerts when relevant judgments are published.

## Architecture

- **Frontend**: Next.js 14 + TypeScript + shadcn/ui + Tailwind CSS (`apps/web/`)
- **Worker**: Python 3.11+ polling engine with APScheduler (`apps/worker/`)
- **Database**: Supabase (PostgreSQL) with real-time subscriptions (`supabase/`)
- **Data Source**: Indian Kanoon API

## Quick Start

### Frontend

```bash
cd apps/web
bun install
bun run dev   # http://localhost:3000
```

### Worker

```bash
cd apps/worker
pip install -e ".[dev]"
cp .env.example .env  # fill in credentials
python -m vigil.main
```

### Database

Run the migration in your Supabase project:

```bash
supabase db push
```

Or manually execute `supabase/migrations/001_initial_schema.sql` in the Supabase SQL editor.

## Environment Variables

See `apps/web/.env.local.example` and `apps/worker/.env.example` for required configuration.
