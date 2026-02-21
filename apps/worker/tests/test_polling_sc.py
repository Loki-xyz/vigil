"""
Tests for sc_scrape_cycle() and sc_scrape_for_watch() in vigil.polling.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vigil.sc_client import SCCaptchaError, SCOrderRecord, SCPDFDownloadError, SCScraperError


# ── Helpers ──────────────────────────────────────────────


def _make_sc_watch(watch_id: str = "w1", watch_type: str = "entity",
                    query_terms: str = "Amazon Web Services") -> dict:
    return {
        "id": watch_id,
        "name": "AWS SC Watch",
        "watch_type": watch_type,
        "query_terms": query_terms,
        "court_filter": ["supremecourt"],
        "is_active": True,
        "polling_interval_minutes": 120,
        "last_polled_at": None,
        "last_poll_result_count": 0,
    }


def _make_non_sc_watch(watch_id: str = "w2") -> dict:
    return {
        "id": watch_id,
        "name": "Delhi HC Watch",
        "watch_type": "entity",
        "query_terms": "Reliance Industries",
        "court_filter": ["delhi"],
        "is_active": True,
        "polling_interval_minutes": 120,
        "last_polled_at": None,
        "last_poll_result_count": 0,
    }


def _make_sc_order(
    case_number: str = "SLP(C) No. 12345/2025",
    diary_number: str = "12345-2025",
    parties: str = "Amazon Web Services Inc. vs Union of India",
) -> SCOrderRecord:
    return SCOrderRecord(
        case_number=case_number,
        diary_number=diary_number,
        parties=parties,
        order_date=date(2026, 2, 21),
        pdf_url="https://www.sci.gov.in/pdf/order.pdf",
    )


# ── sc_scrape_for_watch Tests ────────────────────────────


class TestScScrapeForWatch:
    """Tests for sc_scrape_for_watch — single-watch SC scrape for Poll Now."""

    async def test_happy_path(self, test_settings):
        """Fetches orders, matches, processes, returns new matches."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch()
        order = _make_sc_order()

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[order])

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=False),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock,
                  return_value=[{"id": "wm-1"}]) as mock_process,
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.return_value = MatchResult(
                is_match=True, relevance_score=0.9,
                matched_terms=["Amazon Web Services"],
                snippet="...Amazon Web Services...",
            )

            result = await sc_scrape_for_watch(watch)

        assert len(result) == 1
        assert result[0]["id"] == "wm-1"
        mock_client.fetch_daily_orders.assert_called_once()
        mock_process.assert_called_once()

    async def test_no_orders_returns_empty(self, test_settings):
        """fetch_daily_orders returns [] -> returns [] immediately."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch()
        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[])

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            result = await sc_scrape_for_watch(watch)

        assert result == []

    async def test_no_match_returns_empty(self, test_settings):
        """Orders exist but none match -> returns []."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch(query_terms="Nonexistent Corp")
        order = _make_sc_order(parties="X vs Y")

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[order])

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=False),
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.return_value = MatchResult(is_match=False, relevance_score=0.0)

            result = await sc_scrape_for_watch(watch)

        assert result == []

    async def test_phase2_pdf_download(self, test_settings):
        """Phase 1 no match + needs_pdf -> downloads PDF, phase 2 matches."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch(watch_type="topic", query_terms="transfer pricing")
        order = _make_sc_order(parties="X vs Y")

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[order])
        mock_client.download_and_parse_pdf = AsyncMock(
            return_value="Order about transfer pricing norms."
        )

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=True),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock,
                  return_value=[{"id": "wm-2"}]),
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.side_effect = [
                MatchResult(is_match=False, relevance_score=0.0),
                MatchResult(is_match=True, relevance_score=0.7,
                           matched_terms=["transfer", "pricing"],
                           snippet="...transfer pricing..."),
            ]

            result = await sc_scrape_for_watch(watch)

        assert len(result) == 1
        mock_client.download_and_parse_pdf.assert_called_once()

    async def test_pdf_download_failure_continues(self, test_settings):
        """PDF download error -> phase 2 skipped, no crash, returns []."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch(watch_type="topic", query_terms="transfer pricing")
        order = _make_sc_order(parties="X vs Y")

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[order])
        mock_client.download_and_parse_pdf = AsyncMock(
            side_effect=SCPDFDownloadError("timeout")
        )

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=True),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock) as mock_process,
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.return_value = MatchResult(is_match=False, relevance_score=0.0)

            result = await sc_scrape_for_watch(watch)

        assert result == []
        mock_process.assert_not_called()

    async def test_captcha_error_returns_empty(self, test_settings):
        """SCCaptchaError -> returns [], does not raise."""
        from vigil.polling import sc_scrape_for_watch

        watch = _make_sc_watch()
        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(
            side_effect=SCCaptchaError("captcha failed")
        )

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            result = await sc_scrape_for_watch(watch)

        assert result == []

    async def test_does_not_increment_circuit_breaker(self, test_settings):
        """Errors do NOT touch _sc_consecutive_failures."""
        from vigil import polling
        from vigil.polling import sc_scrape_for_watch

        assert polling._sc_consecutive_failures == 0

        watch = _make_sc_watch()
        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(
            side_effect=SCScraperError("website down")
        )

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            await sc_scrape_for_watch(watch)

        assert polling._sc_consecutive_failures == 0

    async def test_date_range_uses_lookback(self, test_settings):
        """from_date uses sc_lookback_days, to_date is today."""
        from vigil.polling import sc_scrape_for_watch

        test_settings.sc_lookback_days = 3

        watch = _make_sc_watch()
        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[])

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            await sc_scrape_for_watch(watch)

        call_args = mock_client.fetch_daily_orders.call_args
        from_date = call_args[0][0]
        to_date = call_args[0][1]

        expected_from = (datetime.now(timezone.utc) - timedelta(days=3)).date()
        expected_to = datetime.now(timezone.utc).date()
        assert from_date == expected_from
        assert to_date == expected_to


# ── sc_scrape_cycle Tests ────────────────────────────────


class TestScScrapeCycle:
    async def test_disabled_skips(self, patch_supabase, test_settings):
        """When sc_scraper_enabled=False, does nothing."""
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = False
        await sc_scrape_cycle()
        # Should not call supabase at all
        patch_supabase.table.assert_not_called()

    async def test_no_sc_watches_skips(self, patch_supabase, test_settings):
        """When no watches have 'supremecourt' in court_filter, does nothing."""
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[_make_non_sc_watch()]
        )

        with patch("vigil.polling._get_sc_client") as mock_get_client:
            await sc_scrape_cycle()
            mock_get_client.assert_not_called()

    async def test_fetches_and_matches_orders(self, patch_supabase, test_settings):
        """Full happy path: fetch orders, match against SC watches, create judgments."""
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        sc_watch = _make_sc_watch()
        sc_order = _make_sc_order()

        # Mock watches query
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[sc_watch]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[sc_order])

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=False),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock,
                  return_value=[{"id": "m1"}]) as mock_process,
            patch("vigil.polling.dispatch_pending_notifications", new_callable=AsyncMock),
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.return_value = MatchResult(
                is_match=True, relevance_score=0.9,
                matched_terms=["Amazon Web Services"],
                snippet="...Amazon Web Services...",
            )

            await sc_scrape_cycle()

            mock_client.fetch_daily_orders.assert_called_once()
            mock_process.assert_called_once()

    async def test_phase2_downloads_pdf_when_needed(self, patch_supabase, test_settings):
        """When needs_pdf_download returns True, downloads and re-matches."""
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        topic_watch = _make_sc_watch(
            watch_type="topic", query_terms="transfer pricing"
        )
        sc_order = _make_sc_order(parties="X vs Y")

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[topic_watch]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[sc_order])
        mock_client.download_and_parse_pdf = AsyncMock(
            return_value="Order about transfer pricing norms."
        )

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=True),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock,
                  return_value=[]) as mock_process,
            patch("vigil.polling.dispatch_pending_notifications", new_callable=AsyncMock),
        ):
            from vigil.sc_matcher import MatchResult
            # Phase 1: no match (no full text)
            # Phase 2: match (with full text)
            mock_match.side_effect = [
                MatchResult(is_match=False, relevance_score=0.0),
                MatchResult(is_match=True, relevance_score=0.7,
                           matched_terms=["transfer", "pricing"],
                           snippet="...transfer pricing..."),
            ]

            await sc_scrape_cycle()

            mock_client.download_and_parse_pdf.assert_called_once()
            mock_process.assert_called_once()

    async def test_captcha_error_increments_failures(self, patch_supabase, test_settings):
        """Captcha failures increment the circuit breaker counter."""
        from vigil import polling
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[_make_sc_watch()]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(
            side_effect=SCCaptchaError("captcha failed")
        )

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            await sc_scrape_cycle()

        assert polling._sc_consecutive_failures == 1

    async def test_circuit_breaker_sends_admin_alert(self, patch_supabase, test_settings):
        """After 3 consecutive failures, sends an admin alert."""
        from vigil import polling
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        # Pre-set to 2 failures
        polling._sc_consecutive_failures = 2

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[_make_sc_watch()]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(
            side_effect=SCScraperError("website down")
        )

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.send_admin_alert", new_callable=AsyncMock) as mock_alert,
        ):
            await sc_scrape_cycle()

        assert polling._sc_consecutive_failures == 3
        mock_alert.assert_called_once()
        assert "SC Website Scraper" in mock_alert.call_args[0][0]

    async def test_success_resets_failure_counter(self, patch_supabase, test_settings):
        """A successful scrape resets the consecutive failure counter."""
        from vigil import polling
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        polling._sc_consecutive_failures = 2

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[_make_sc_watch()]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[])

        with patch("vigil.polling._get_sc_client", return_value=mock_client):
            await sc_scrape_cycle()

        assert polling._sc_consecutive_failures == 0

    async def test_order_processing_error_continues(self, patch_supabase, test_settings):
        """Error processing one order shouldn't stop processing others."""
        from vigil.polling import sc_scrape_cycle
        test_settings.sc_scraper_enabled = True

        sc_watch = _make_sc_watch()
        order1 = _make_sc_order(case_number="Case 1", parties="Amazon Web Services vs Y")
        order2 = _make_sc_order(case_number="Case 2", parties="Amazon Web Services vs Z")

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[sc_watch]
        )

        mock_client = AsyncMock()
        mock_client.fetch_daily_orders = AsyncMock(return_value=[order1, order2])

        with (
            patch("vigil.polling._get_sc_client", return_value=mock_client),
            patch("vigil.polling.match_order_against_watch") as mock_match,
            patch("vigil.polling.needs_pdf_download", return_value=False),
            patch("vigil.polling.process_sc_orders", new_callable=AsyncMock,
                  side_effect=[Exception("DB error"), [{"id": "m2"}]]) as mock_process,
            patch("vigil.polling.dispatch_pending_notifications", new_callable=AsyncMock),
        ):
            from vigil.sc_matcher import MatchResult
            mock_match.return_value = MatchResult(
                is_match=True, relevance_score=0.9,
                matched_terms=["Amazon Web Services"], snippet="...",
            )

            await sc_scrape_cycle()

            # Should have been called for both orders
            assert mock_process.call_count == 2


# ── Scheduler Setup ──────────────────────────────────────


class TestSchedulerSetup:
    def test_sc_jobs_added_when_enabled(self, test_settings):
        from vigil.polling import setup_scheduler
        test_settings.sc_scraper_enabled = True
        test_settings.sc_scrape_schedule_hours = "8,17"

        scheduler = setup_scheduler()
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "sc_scrape_8" in job_ids
        assert "sc_scrape_17" in job_ids

    def test_sc_jobs_not_added_when_disabled(self, test_settings):
        from vigil.polling import setup_scheduler
        test_settings.sc_scraper_enabled = False

        scheduler = setup_scheduler()
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert not any(jid.startswith("sc_scrape") for jid in job_ids)


# ── SC Client Singleton ──────────────────────────────────


class TestGetScClient:
    def test_lazy_init(self, test_settings):
        from vigil import polling
        from vigil.polling import _get_sc_client

        test_settings.sc_scraper_enabled = True
        polling._sc_client = None

        client = _get_sc_client()
        assert client is not None
        assert polling._sc_client is client

        # Second call returns same instance
        client2 = _get_sc_client()
        assert client2 is client

        # Cleanup
        polling._sc_client = None
