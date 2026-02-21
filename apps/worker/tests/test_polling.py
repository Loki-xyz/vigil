"""Tests for vigil/polling.py — poll_single_watch, poll_cycle, check_poll_requests, setup_scheduler."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vigil.ik_client import IKAPIAuthError, IKAPIRateLimitError
from vigil.polling import (
    check_poll_requests,
    poll_cycle,
    poll_single_watch,
    setup_scheduler,
)


# ============================================================================
# poll_single_watch
# ============================================================================


@pytest.mark.unit
class TestPollSingleWatch:
    """Tests for poll_single_watch — build_query -> search -> process -> update."""

    async def test_full_flow(self, patch_supabase, sample_watch_entity):
        """build_query, search, process_search_results all called; returns matches."""
        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "found": 1,
            "docs": [{"tid": 100, "title": "Test"}],
        }

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="test query") as mock_bq,
            patch(
                "vigil.polling.process_search_results",
                new_callable=AsyncMock,
                return_value=[{"id": "wm-1"}],
            ) as mock_psr,
        ):
            result = await poll_single_watch(sample_watch_entity)

        mock_bq.assert_called_once()
        mock_client.search.assert_called_once()
        mock_psr.assert_called_once()
        assert len(result) == 1

    async def test_updates_last_polled_at(
        self, patch_supabase, sample_watch_entity
    ):
        """Watch.last_polled_at updated after polling."""
        mock_client = AsyncMock()
        mock_client.search.return_value = {"found": 0, "docs": []}

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q"),
            patch(
                "vigil.polling.process_search_results",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await poll_single_watch(sample_watch_entity)

        patch_supabase.table.assert_any_call("watches")
        update_calls = patch_supabase.table.return_value.update.call_args_list
        assert len(update_calls) > 0
        update_data = update_calls[-1][0][0]
        assert "last_polled_at" in update_data

    async def test_from_date_from_last_polled_at(
        self, patch_supabase, sample_watch_entity
    ):
        """last_polled_at -> from_date for build_query."""
        sample_watch_entity["last_polled_at"] = "2026-02-15T10:00:00+00:00"

        mock_client = AsyncMock()
        mock_client.search.return_value = {"found": 0, "docs": []}

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q") as mock_bq,
            patch(
                "vigil.polling.process_search_results",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await poll_single_watch(sample_watch_entity)

        from_date_arg = mock_bq.call_args[0][3]
        assert from_date_arg == date(2026, 2, 15)

    async def test_from_date_lookback_when_never_polled(
        self, patch_supabase, sample_watch_entity
    ):
        """last_polled_at=None -> uses now minus lookback days as from_date."""
        sample_watch_entity["last_polled_at"] = None

        mock_client = AsyncMock()
        mock_client.search.return_value = {"found": 0, "docs": []}

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q") as mock_bq,
            patch(
                "vigil.polling.process_search_results",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await poll_single_watch(sample_watch_entity)

        from_date_arg = mock_bq.call_args[0][3]
        expected = (datetime.now(timezone.utc) - timedelta(days=4)).date()
        assert from_date_arg == expected

    async def test_general_error_returns_empty(
        self, patch_supabase, sample_watch_entity
    ):
        """Non-auth exception -> caught, returns []."""
        mock_client = AsyncMock()
        mock_client.search.side_effect = Exception("Network error")

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q"),
        ):
            result = await poll_single_watch(sample_watch_entity)

        assert result == []

    async def test_auth_error_propagates(
        self, patch_supabase, sample_watch_entity
    ):
        """IKAPIAuthError -> re-raised, not swallowed."""
        mock_client = AsyncMock()
        mock_client.search.side_effect = IKAPIAuthError("403 Forbidden")

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q"),
        ):
            with pytest.raises(IKAPIAuthError):
                await poll_single_watch(sample_watch_entity)

    async def test_rate_limit_error_sets_backoff(
        self, patch_supabase, sample_watch_entity
    ):
        """IKAPIRateLimitError -> watch added to backoff dict, returns []."""
        from vigil import polling

        mock_client = AsyncMock()
        mock_client.search.side_effect = IKAPIRateLimitError("429")

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q"),
        ):
            result = await poll_single_watch(sample_watch_entity)

        assert result == []
        assert sample_watch_entity["id"] in polling._watch_backoffs

    async def test_rate_limit_backoff_duration_is_doubled_interval(
        self, patch_supabase, sample_watch_entity
    ):
        """Backoff duration should be 2x the watch's polling_interval_minutes."""
        from vigil import polling

        sample_watch_entity["polling_interval_minutes"] = 60
        mock_client = AsyncMock()
        mock_client.search.side_effect = IKAPIRateLimitError("429")

        with (
            patch("vigil.polling._get_ik_client", return_value=mock_client),
            patch("vigil.polling.build_query", return_value="q"),
        ):
            await poll_single_watch(sample_watch_entity)

        backoff_until = polling._watch_backoffs[sample_watch_entity["id"]]
        expected_min = timedelta(minutes=120)
        actual_delta = backoff_until - datetime.now(timezone.utc)
        # Allow 5 seconds tolerance
        assert actual_delta > expected_min - timedelta(seconds=5)


# ============================================================================
# poll_cycle
# ============================================================================


def _make_watches(count, **overrides):
    """Helper to create watch dicts for poll_cycle tests."""
    watches = []
    for i in range(1, count + 1):
        w = {
            "id": f"w{i}",
            "name": f"Watch {i}",
            "watch_type": "entity",
            "query_terms": "test",
            "polling_interval_minutes": 30,
            "last_polled_at": None,
            "created_at": "2026-02-10T00:00:00+00:00",
        }
        w.update(overrides)
        watches.append(w)
    return watches


@pytest.mark.unit
class TestPollCycle:
    """Tests for poll_cycle — fetch active watches, poll due ones, dispatch."""

    async def test_polls_all_due_watches(self, patch_supabase):
        """3 active watches with no last_polled_at -> all 3 polled."""
        watches = _make_watches(3)
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_poll,
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
        ):
            await poll_cycle()

        assert mock_poll.call_count == 3

    async def test_only_elapsed_intervals_polled(self, patch_supabase):
        """Only watches whose interval has elapsed should be polled."""
        now = datetime.now(timezone.utc)
        watches = [
            {
                "id": "w1",
                "name": "W1",
                "watch_type": "entity",
                "query_terms": "test",
                "polling_interval_minutes": 30,
                "last_polled_at": (now - timedelta(minutes=45)).isoformat(),
                "created_at": "2026-02-10T00:00:00+00:00",
            },
            {
                "id": "w2",
                "name": "W2",
                "watch_type": "entity",
                "query_terms": "test",
                "polling_interval_minutes": 30,
                "last_polled_at": (now - timedelta(minutes=5)).isoformat(),
                "created_at": "2026-02-10T00:00:00+00:00",
            },
        ]
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_poll,
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
        ):
            await poll_cycle()

        assert mock_poll.call_count == 1
        polled_watch = mock_poll.call_args[0][0]
        assert polled_watch["id"] == "w1"

    async def test_continues_on_failure(self, patch_supabase):
        """Watch 2 errors -> watches 1,3 still polled."""
        watches = _make_watches(3)
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        call_count = {"value": 0}

        async def side_effect(watch):
            call_count["value"] += 1
            if watch["id"] == "w2":
                raise Exception("Search failed")
            return []

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                side_effect=side_effect,
            ),
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
        ):
            await poll_cycle()

        assert call_count["value"] == 3

    async def test_halts_on_auth_error(self, patch_supabase):
        """Watch 2 gets 403 -> watch 3 NOT polled."""
        watches = _make_watches(3)
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        call_order = []

        async def side_effect(watch):
            call_order.append(watch["id"])
            if watch["id"] == "w2":
                raise IKAPIAuthError("403 Forbidden")
            return []

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                side_effect=side_effect,
            ),
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
        ):
            await poll_cycle()

        assert "w3" not in call_order

    async def test_triggers_dispatch(self, patch_supabase):
        """dispatch_pending_notifications called after polling."""
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch(
            "vigil.polling.dispatch_pending_notifications",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            await poll_cycle()

        mock_dispatch.assert_called_once()

    async def test_403_sends_admin_alert(self, patch_supabase):
        """IKAPIAuthError in poll_cycle -> send_admin_alert called."""
        watches = _make_watches(1)
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        async def raise_auth(watch):
            raise IKAPIAuthError("403 Forbidden")

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                side_effect=raise_auth,
            ),
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
            patch(
                "vigil.polling.send_admin_alert",
                new_callable=AsyncMock,
            ) as mock_admin_alert,
        ):
            await poll_cycle()

        mock_admin_alert.assert_called_once()
        call_args = mock_admin_alert.call_args
        assert "403" in str(call_args)

    async def test_supabase_down_cycle_returns_gracefully(self, patch_supabase):
        """Supabase failure on fetch watches -> logs error, returns."""
        patch_supabase.table.return_value.execute.side_effect = Exception(
            "Supabase connection refused"
        )

        with patch(
            "vigil.polling.dispatch_pending_notifications",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            # Should not raise
            await poll_cycle()

        # dispatch should NOT be called since we returned early
        mock_dispatch.assert_not_called()

    async def test_backed_off_watch_skipped(self, patch_supabase):
        """Watch in backoff dict -> not polled even if interval elapsed."""
        from vigil import polling

        watches = _make_watches(2)
        # Put watch 1 in backoff
        polling._watch_backoffs[watches[0]["id"]] = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )

        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=watches
        )

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_poll,
            patch(
                "vigil.polling.dispatch_pending_notifications",
                new_callable=AsyncMock,
            ),
        ):
            await poll_cycle()

        # Only watch 2 should be polled
        assert mock_poll.call_count == 1
        polled_watch = mock_poll.call_args[0][0]
        assert polled_watch["id"] == watches[1]["id"]


# ============================================================================
# check_poll_requests
# ============================================================================


@pytest.mark.unit
class TestCheckPollRequests:
    """Tests for check_poll_requests — process pending 'Poll Now' requests."""

    async def test_processes_pending_to_done(
        self, patch_supabase, sample_watch_entity
    ):
        """status=pending -> polls watch, status -> done."""
        poll_req = {
            "id": "pr-1",
            "watch_id": sample_watch_entity["id"],
            "status": "pending",
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[poll_req]),  # fetch pending
            MagicMock(data=[{}]),  # update processing
            MagicMock(data=sample_watch_entity),  # fetch watch
            MagicMock(data=[{}]),  # update done
        ]

        with patch(
            "vigil.polling.poll_single_watch",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await check_poll_requests()

        update_calls = patch_supabase.table.return_value.update.call_args_list
        assert any("done" in str(c) for c in update_calls)

    async def test_marks_failed_on_error(
        self, patch_supabase, sample_watch_entity
    ):
        """Poll errors -> status=failed."""
        poll_req = {
            "id": "pr-1",
            "watch_id": sample_watch_entity["id"],
            "status": "pending",
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[poll_req]),  # fetch pending
            MagicMock(data=[{}]),  # update processing
            MagicMock(data=sample_watch_entity),  # fetch watch
            # poll_single_watch raises, then:
            MagicMock(data=[{}]),  # update failed
        ]

        with patch(
            "vigil.polling.poll_single_watch",
            new_callable=AsyncMock,
            side_effect=Exception("Search failed"),
        ):
            await check_poll_requests()

        update_calls = patch_supabase.table.return_value.update.call_args_list
        assert any("failed" in str(c) for c in update_calls)

    async def test_ignores_when_no_pending(self, patch_supabase):
        """No pending requests -> no polling."""
        patch_supabase.table.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch(
            "vigil.polling.poll_single_watch", new_callable=AsyncMock
        ) as mock_poll:
            await check_poll_requests()

        mock_poll.assert_not_called()

    async def test_sc_watch_uses_scraper_not_ik(
        self, patch_supabase, sample_watch_entity, test_settings
    ):
        """SC watch + scraper enabled -> uses sc_scrape_for_watch, NOT poll_single_watch."""
        test_settings.sc_scraper_enabled = True
        # sample_watch_entity has court_filter=["supremecourt", "delhi"]
        poll_req = {
            "id": "pr-1",
            "watch_id": sample_watch_entity["id"],
            "status": "pending",
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[poll_req]),  # fetch pending
            MagicMock(data=[{}]),  # update processing
            MagicMock(data=sample_watch_entity),  # fetch watch
            MagicMock(data=[{}]),  # update done
        ]

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_ik_poll,
            patch(
                "vigil.polling.sc_scrape_for_watch",
                new_callable=AsyncMock,
                return_value=[{"id": "sc-m1"}],
            ) as mock_sc_scrape,
        ):
            await check_poll_requests()

        mock_sc_scrape.assert_called_once_with(sample_watch_entity)
        mock_ik_poll.assert_not_called()

    async def test_non_sc_watch_uses_ik_not_scraper(
        self, patch_supabase, test_settings
    ):
        """Non-SC watch -> uses poll_single_watch (IK API), NOT sc_scrape_for_watch."""
        test_settings.sc_scraper_enabled = True
        delhi_watch = {
            "id": "w-delhi",
            "name": "Delhi Watch",
            "watch_type": "entity",
            "query_terms": "test",
            "court_filter": ["delhi"],
            "is_active": True,
        }
        poll_req = {
            "id": "pr-2",
            "watch_id": "w-delhi",
            "status": "pending",
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[poll_req]),  # fetch pending
            MagicMock(data=[{}]),  # update processing
            MagicMock(data=delhi_watch),  # fetch watch
            MagicMock(data=[{}]),  # update done
        ]

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_ik_poll,
            patch(
                "vigil.polling.sc_scrape_for_watch",
                new_callable=AsyncMock,
            ) as mock_sc_scrape,
        ):
            await check_poll_requests()

        mock_ik_poll.assert_called_once()
        mock_sc_scrape.assert_not_called()

    async def test_sc_scraper_disabled_falls_back_to_ik(
        self, patch_supabase, sample_watch_entity, test_settings
    ):
        """SC watch but scraper disabled -> falls back to poll_single_watch (IK API)."""
        test_settings.sc_scraper_enabled = False
        poll_req = {
            "id": "pr-3",
            "watch_id": sample_watch_entity["id"],
            "status": "pending",
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[poll_req]),  # fetch pending
            MagicMock(data=[{}]),  # update processing
            MagicMock(data=sample_watch_entity),  # fetch watch
            MagicMock(data=[{}]),  # update done
        ]

        with (
            patch(
                "vigil.polling.poll_single_watch",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_ik_poll,
            patch(
                "vigil.polling.sc_scrape_for_watch",
                new_callable=AsyncMock,
            ) as mock_sc_scrape,
        ):
            await check_poll_requests()

        mock_ik_poll.assert_called_once()
        mock_sc_scrape.assert_not_called()


# ============================================================================
# setup_scheduler
# ============================================================================


@pytest.mark.unit
class TestSetupScheduler:
    """Tests for setup_scheduler — APScheduler job configuration."""

    def test_returns_scheduler_instance(self):
        """Returns an AsyncIOScheduler."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = setup_scheduler()
        assert isinstance(scheduler, AsyncIOScheduler)

    def test_has_four_jobs(self):
        """4 jobs configured: poll_cycle, dispatch, digest, check_poll_requests."""
        scheduler = setup_scheduler()
        assert len(scheduler.get_jobs()) == 4

    def test_poll_cycle_interval_30min(self):
        """poll_cycle every 30 minutes."""
        scheduler = setup_scheduler()
        jobs = scheduler.get_jobs()
        poll_jobs = [j for j in jobs if "poll_cycle" in j.name]
        assert len(poll_jobs) == 1
        assert poll_jobs[0].trigger.interval == timedelta(minutes=30)

    def test_dispatch_interval_10min(self):
        """dispatch_pending_notifications every 10 minutes."""
        scheduler = setup_scheduler()
        jobs = scheduler.get_jobs()
        dispatch_jobs = [j for j in jobs if "dispatch" in j.name]
        assert len(dispatch_jobs) == 1
        assert dispatch_jobs[0].trigger.interval == timedelta(minutes=10)

    def test_check_poll_requests_interval_30s(self):
        """check_poll_requests every 30 seconds."""
        scheduler = setup_scheduler()
        jobs = scheduler.get_jobs()
        poll_req_jobs = [j for j in jobs if "check_poll_requests" in j.name]
        assert len(poll_req_jobs) == 1
        assert poll_req_jobs[0].trigger.interval == timedelta(seconds=30)

    def test_digest_cron_at_9am(self):
        """send_daily_digest cron at 09:00."""
        scheduler = setup_scheduler()
        jobs = scheduler.get_jobs()
        digest_jobs = [j for j in jobs if "digest" in j.name]
        assert len(digest_jobs) == 1
        trigger = digest_jobs[0].trigger
        fields = {f.name: f for f in trigger.fields}
        assert str(fields["hour"]) == "9"
        assert str(fields["minute"]) == "0"
