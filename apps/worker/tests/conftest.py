"""
Shared fixtures for Vigil worker tests.

Strategy:
- Mock Supabase client globally (no real DB calls in unit tests)
- Provide realistic IK API response fixtures
- Provide watch/judgment factory helpers
- Override settings with test-safe defaults
"""

from __future__ import annotations

import os

# Set dummy env vars BEFORE any vigil module is imported.
# This prevents config.py and supabase_client.py from failing at import time.
os.environ.setdefault("VIGIL_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("VIGIL_SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("VIGIL_IK_API_TOKEN", "test-token")

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Supabase Client Mock ──────────────────────────────────


@pytest.fixture
def mock_supabase():
    """
    Chainable MagicMock mimicking supabase.from_().select().eq()...execute().
    """
    client = MagicMock()

    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.insert.return_value = table_mock
    table_mock.update.return_value = table_mock
    table_mock.upsert.return_value = table_mock
    table_mock.delete.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.neq.return_value = table_mock
    table_mock.lt.return_value = table_mock
    table_mock.lte.return_value = table_mock
    table_mock.gte.return_value = table_mock
    table_mock.is_.return_value = table_mock
    table_mock.in_.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.single.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[], count=0)

    client.table.return_value = table_mock
    client.from_.return_value = table_mock

    return client


@pytest.fixture
def patch_supabase(mock_supabase):
    """Patches the supabase singleton across all worker modules."""
    with (
        patch("vigil.supabase_client.supabase", mock_supabase),
        patch("vigil.matcher.supabase", mock_supabase, create=True),
        patch("vigil.polling.supabase", mock_supabase, create=True),
        patch("vigil.notifier.supabase", mock_supabase, create=True),
        patch("vigil.ik_client.supabase", mock_supabase, create=True),
        patch("vigil.sc_client.supabase", mock_supabase, create=True),
    ):
        yield mock_supabase


# ── IK API Response Fixtures ──────────────────────────────


@pytest.fixture
def ik_search_response_single():
    """Single-result IK search response."""
    return {
        "found": 1,
        "docs": [
            {
                "tid": 12345678,
                "title": "Amazon Web Services Inc. vs Commissioner of Income Tax",
                "docsource": "Delhi High Court",
                "headline": "...cloud computing services <b>Amazon</b>...",
                "publishdate": "2026-02-17",
                "numcites": 5,
                "docsize": 24000,
            }
        ],
    }


@pytest.fixture
def ik_search_response_multiple():
    """Multi-result IK search response (3 docs)."""
    return {
        "found": 3,
        "docs": [
            {
                "tid": 12345678,
                "title": "Amazon Web Services Inc. vs Commissioner of Income Tax",
                "docsource": "Delhi High Court",
                "headline": "...cloud computing services...",
                "publishdate": "2026-02-17",
                "numcites": 5,
                "docsize": 24000,
            },
            {
                "tid": 23456789,
                "title": "M/s AWS India Pvt Ltd vs Union of India",
                "docsource": "Supreme Court of India",
                "headline": "...data localisation...",
                "publishdate": "2026-02-16",
                "numcites": 12,
                "docsize": 45000,
            },
            {
                "tid": 34567890,
                "title": "In Re: Cloud Services Data Localisation",
                "docsource": "Karnataka High Court",
                "headline": "...IT Act compliance...",
                "publishdate": "2026-02-15",
                "numcites": 3,
                "docsize": 18000,
            },
        ],
    }


@pytest.fixture
def ik_search_response_empty():
    """Empty IK search response."""
    return {"found": 0, "docs": []}


@pytest.fixture
def ik_docmeta_response():
    """IK document metadata response."""
    return {
        "tid": 12345678,
        "title": "Amazon Web Services Inc. vs Commissioner of Income Tax",
        "bench": ["Justice A. Kumar", "Justice B. Singh"],
        "acts_cited": ["Income Tax Act, 1961", "Information Technology Act, 2000"],
        "ai_tags": ["cloud computing", "transfer pricing", "PE"],
    }


# ── Watch Fixtures ─────────────────────────────────────────


@pytest.fixture
def sample_watch_entity():
    """An entity-type watch for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "AWS Judgments",
        "watch_type": "entity",
        "query_terms": "Amazon Web Services",
        "query_template": None,
        "court_filter": ["supremecourt", "delhi"],
        "is_active": True,
        "polling_interval_minutes": 120,
        "last_polled_at": "2026-02-17T10:00:00+00:00",
        "last_poll_result_count": 0,
        "created_at": "2026-02-01T00:00:00+00:00",
        "updated_at": "2026-02-17T10:00:00+00:00",
    }


@pytest.fixture
def sample_watch_topic():
    """A topic-type watch for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "DTAA Mauritius",
        "watch_type": "topic",
        "query_terms": "India Mauritius DTAA",
        "query_template": None,
        "court_filter": ["supremecourt"],
        "is_active": True,
        "polling_interval_minutes": 240,
        "last_polled_at": None,
        "last_poll_result_count": 0,
        "created_at": "2026-02-10T00:00:00+00:00",
        "updated_at": "2026-02-10T00:00:00+00:00",
    }


@pytest.fixture
def sample_watch_act():
    """An act-type watch for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "IT Act Watch",
        "watch_type": "act",
        "query_terms": "Information Technology Act",
        "query_template": None,
        "court_filter": [],
        "is_active": True,
        "polling_interval_minutes": 720,
        "last_polled_at": "2026-02-16T06:00:00+00:00",
        "last_poll_result_count": 2,
        "created_at": "2026-02-05T00:00:00+00:00",
        "updated_at": "2026-02-16T06:00:00+00:00",
    }


# ── Backoff State Reset ───────────────────────────────────


@pytest.fixture(autouse=True)
def reset_watch_backoffs():
    """Clear in-memory backoff state between tests."""
    from vigil import polling
    polling._watch_backoffs.clear()
    polling._sc_consecutive_failures = 0
    yield
    polling._watch_backoffs.clear()
    polling._sc_consecutive_failures = 0


# ── SMTP / Slack Mocks ────────────────────────────────────


@pytest.fixture
def mock_smtp():
    """Mock aiosmtplib.SMTP for email tests."""
    with patch("vigil.notifier.aiosmtplib") as aiosmtplib_mod:
        smtp_instance = AsyncMock()
        aiosmtplib_mod.SMTP.return_value = smtp_instance
        smtp_instance.connect = AsyncMock()
        smtp_instance.starttls = AsyncMock()
        smtp_instance.login = AsyncMock()
        smtp_instance.send_message = AsyncMock()
        smtp_instance.quit = AsyncMock()
        yield smtp_instance


@pytest.fixture
def mock_slack_webhook():
    """Mock httpx.AsyncClient for Slack webhook POST."""
    with patch("vigil.notifier.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="ok")
        )
        yield client


# ── Settings Override ──────────────────────────────────────


@pytest.fixture
def test_settings():
    """Settings with test-safe defaults — patches across all worker modules."""
    with patch("vigil.config.settings") as mock_settings:
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-service-role-key"
        mock_settings.ik_api_token = "test-ik-token"
        mock_settings.ik_api_base_url = "https://api.indiankanoon.org"
        mock_settings.ik_api_timeout_seconds = 5
        mock_settings.ik_api_max_retries = 3
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 1025
        mock_settings.smtp_username = "test"
        mock_settings.smtp_password = "test"
        mock_settings.smtp_from_email = "vigil@test.com"
        mock_settings.smtp_use_tls = False
        mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
        mock_settings.polling_enabled = True
        mock_settings.first_poll_lookback_days = 4
        mock_settings.timezone = "Asia/Kolkata"
        mock_settings.notification_email_enabled = True
        mock_settings.notification_slack_enabled = False
        mock_settings.notification_email_recipients = ""
        mock_settings.daily_digest_enabled = True
        # SC scraper settings
        mock_settings.sc_scraper_enabled = False
        mock_settings.sc_scrape_schedule_hours = "8,17"
        mock_settings.sc_base_url = "https://www.sci.gov.in"
        mock_settings.sc_request_timeout_seconds = 10
        mock_settings.sc_max_retries = 2
        mock_settings.sc_captcha_max_attempts = 2
        mock_settings.sc_rate_limit_seconds = 0.01
        mock_settings.sc_lookback_days = 2
        mock_settings.sc_pdf_download_enabled = True
        mock_settings.sc_captcha_debug_dir = ""
        mock_settings.tesseract_cmd = "tesseract"
        # Patch settings in modules that import it directly
        with (
            patch("vigil.notifier.settings", mock_settings, create=True),
            patch("vigil.polling.settings", mock_settings, create=True),
            patch("vigil.sc_client.settings", mock_settings, create=True),
        ):
            yield mock_settings


# ── SC Scraper Fixtures ──────────────────────────────────


@pytest.fixture
def sample_sc_order():
    """A sample SC daily order record."""
    from datetime import date

    from vigil.sc_client import SCOrderRecord

    return SCOrderRecord(
        case_number="SLP(C) No. 12345/2025",
        diary_number="12345-2025",
        parties="Amazon Web Services Inc. vs Union of India",
        order_date=date(2026, 2, 21),
        pdf_url="https://www.sci.gov.in/pdf/order/12345.pdf",
        court="Supreme Court of India",
    )


@pytest.fixture
def sample_sc_pdf_text():
    """Sample extracted text from an SC daily order PDF."""
    return (
        "IN THE SUPREME COURT OF INDIA\n"
        "CIVIL APPELLATE JURISDICTION\n"
        "SLP(C) No. 12345/2025\n\n"
        "Amazon Web Services Inc. ... Petitioner\n"
        "vs.\n"
        "Union of India ... Respondent\n\n"
        "ORDER\n\n"
        "This petition under Article 136 challenges the order of the "
        "Delhi High Court regarding cloud computing services and "
        "Information Technology Act, 2000 compliance.\n"
        "The matter relates to India Mauritius DTAA provisions "
        "and transfer pricing norms applicable to digital services.\n"
    )
