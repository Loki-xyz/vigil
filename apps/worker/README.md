# Vigil Worker

Python polling worker for the Vigil Judgment Intelligence Monitor. Monitors Indian Kanoon API for new Supreme Court and High Court judgments matching configured watches, then dispatches email and Slack alerts.

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your Supabase and IK API credentials
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VIGIL_SUPABASE_URL` | Yes | Supabase project URL |
| `VIGIL_SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (bypasses RLS) |
| `VIGIL_IK_API_TOKEN` | Yes | Indian Kanoon API token |
| `VIGIL_SMTP_HOST` | No | SMTP server for email alerts |
| `VIGIL_SMTP_PORT` | No | SMTP port (default: 587) |
| `VIGIL_SMTP_USERNAME` | No | SMTP username |
| `VIGIL_SMTP_PASSWORD` | No | SMTP password |
| `VIGIL_SMTP_FROM_EMAIL` | No | Sender email address |
| `VIGIL_SLACK_WEBHOOK_URL` | No | Slack incoming webhook URL |
| `VIGIL_POLLING_ENABLED` | No | Master polling switch (default: true) |
| `VIGIL_TIMEZONE` | No | Timezone (default: Asia/Kolkata) |

## Running

```bash
python -m vigil.main
```

The worker starts four scheduled jobs:
- **Poll cycle** — every 30 minutes (polls watches whose interval has elapsed)
- **Notification dispatch** — every 10 minutes
- **Daily digest** — 9:00 AM IST
- **Poll request check** — every 30 seconds (handles "Poll Now" from the dashboard)

## Testing

```bash
# Run all tests
pytest

# Single test file
pytest tests/test_polling.py -v

# Single test
pytest tests/test_polling.py::test_name -v

# With coverage
pytest --cov=vigil
```

## Linting

```bash
ruff check vigil/
ruff format vigil/
```

## Modules

| Module | Purpose |
|--------|---------|
| `config.py` | Pydantic Settings, env vars with `VIGIL_` prefix |
| `supabase_client.py` | Supabase client (service role key) |
| `ik_client.py` | Indian Kanoon API client (rate limiting, retries) |
| `query_builder.py` | Builds IK `formInput` strings from watch config |
| `matcher.py` | Judgment upsert + watch_match deduplication |
| `polling.py` | APScheduler polling engine |
| `notifier.py` | Email (aiosmtplib) + Slack (Block Kit) dispatch |
| `main.py` | Entry point — starts scheduler |
