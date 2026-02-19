-- ============================================================
-- Vigil — Judgment Intelligence Monitor
-- Initial Schema Migration
-- ============================================================

-- ============================================================
-- EXTENSIONS (installed in extensions schema on Supabase)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pg_trgm" SCHEMA "extensions";
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
CREATE INDEX idx_judgments_title_trgm ON judgments USING gin (title extensions.gin_trgm_ops);

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
    retry_count     INTEGER DEFAULT 0,

    CONSTRAINT unique_watch_judgment UNIQUE (watch_id, judgment_id)
);

CREATE INDEX idx_watch_matches_watch_id ON watch_matches(watch_id);
CREATE INDEX idx_watch_matches_judgment_id ON watch_matches(judgment_id);
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

CREATE INDEX idx_notification_log_watch_match_id ON notification_log(watch_match_id);

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
-- POLL_REQUESTS: Queue for "Poll Now" feature
-- ============================================================
CREATE TABLE poll_requests (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    watch_id    UUID NOT NULL REFERENCES watches(id),
    status      VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- UPDATED_AT TRIGGER: Auto-update timestamp
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER watches_updated_at
    BEFORE UPDATE ON watches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- REAL-TIME: Enable for live dashboard updates
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE watches;
ALTER PUBLICATION supabase_realtime ADD TABLE watch_matches;
ALTER PUBLICATION supabase_realtime ADD TABLE poll_requests;
