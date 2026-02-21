"""
Integration tests for the full polling flow.

Wires multiple modules together with mocks only at
the external boundary (IK API via httpx, SMTP).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Sample Data ────────────────────────────────────────────


def _make_watch(name: str, watch_type: str = "entity", **overrides):
    base = {
        "id": str(uuid.uuid4()),
        "name": name,
        "watch_type": watch_type,
        "query_terms": name,
        "query_template": None,
        "court_filter": ["supremecourt"],
        "is_active": True,
        "polling_interval_minutes": 120,
        "last_polled_at": "2026-02-17T00:00:00+00:00",
        "last_poll_result_count": 0,
        "created_at": "2026-02-01T00:00:00+00:00",
        "updated_at": "2026-02-17T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _make_ik_doc(tid: int, title: str, court: str = "Delhi High Court"):
    return {
        "tid": tid,
        "title": title,
        "docsource": court,
        "headline": f"...{title[:30]}...",
        "publishdate": "2026-02-17",
        "numcites": 3,
        "docsize": 20000,
    }


# ── Integration Tests ─────────────────────────────────────


@pytest.mark.integration
class TestFullPollingCycle:
    """End-to-end polling cycle: watches → IK search → match → notify."""

    async def test_full_cycle_two_watches(self, patch_supabase, test_settings):
        """
        2 active watches polled, judgments upserted, matches created,
        notifications dispatched.
        """
        from vigil.polling import poll_cycle

        watch_a = _make_watch("Watch A")
        watch_b = _make_watch("Watch B")
        test_settings.notification_email_enabled = False

        # Sequential execute calls: watches query, then per-watch matcher + update
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[watch_a, watch_b]),  # fetch active watches
            MagicMock(data=[{"id": "j1", "ik_doc_id": 111}]),  # judgment upsert A
            MagicMock(data=[{"id": "wm1"}]),  # match insert A
            MagicMock(data=[{}]),  # watch update A
            MagicMock(data=[{"id": "j2", "ik_doc_id": 222}]),  # judgment upsert B
            MagicMock(data=[{"id": "wm2"}]),  # match insert B
            MagicMock(data=[{}]),  # watch update B
            MagicMock(data=[]),  # dispatch: no unnotified
        ]

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            side_effect=[
                {"found": 1, "docs": [_make_ik_doc(111, "Judgment A")]},
                {"found": 1, "docs": [_make_ik_doc(222, "Judgment B")]},
            ]
        )

        with patch("vigil.polling._get_ik_client", return_value=mock_client):
            await poll_cycle()

        assert mock_client.search.call_count == 2
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        assert len(upsert_calls) >= 2

    async def test_poll_now_flow(self, patch_supabase):
        """
        Pending poll_request → poll watch → status updated to done.
        """
        from vigil.polling import check_poll_requests

        watch = _make_watch("Poll Now Watch", court_filter=["delhi"])
        poll_request = {
            "id": str(uuid.uuid4()),
            "watch_id": watch["id"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Sequential execute calls:
        # 0. stale request cleanup (update status=failed where processing >5min)
        # 1. fetch pending poll_requests
        # 2. mark as processing
        # 3. fetch watch via .single() (returns dict, not list)
        # 4. mark as done
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[]),  # stale request cleanup (none found)
            MagicMock(data=[poll_request]),  # pending poll requests
            MagicMock(data=[{}]),  # update status=processing
            MagicMock(data=watch),  # fetch watch (.single())
            MagicMock(data=[{}]),  # update status=done
        ]

        with patch(
            "vigil.polling.poll_single_watch", new_callable=AsyncMock
        ) as mock_poll:
            mock_poll.return_value = [{"id": "m1"}]

            await check_poll_requests()

            mock_poll.assert_called_once()
            patch_supabase.table.return_value.update.assert_called()

    async def test_dedup_across_watches(self, patch_supabase):
        """
        Two watches match the same judgment (ik_doc_id=111).
        Only 1 judgment record created, but 2 watch_matches.
        """
        from vigil.matcher import process_search_results

        watch_a_id = str(uuid.uuid4())
        watch_b_id = str(uuid.uuid4())
        same_doc = [_make_ik_doc(111, "Shared Judgment")]

        # Set up sequential returns for upsert + insert across both calls
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(
                data=[{"id": "j1", "ik_doc_id": 111}]
            ),  # judgment upsert (watch A)
            MagicMock(data=[{"id": "wm1"}]),  # match insert (watch A)
            MagicMock(
                data=[{"id": "j1", "ik_doc_id": 111}]
            ),  # judgment upsert (watch B, same j1)
            MagicMock(data=[{"id": "wm2"}]),  # match insert (watch B)
        ]

        result_a = await process_search_results(watch_a_id, same_doc)
        result_b = await process_search_results(watch_b_id, same_doc)

        assert len(result_a) >= 1
        assert len(result_b) >= 1

    async def test_403_halts_all_polling(self, patch_supabase):
        """
        Watch 1 succeeds, Watch 2 gets 403 → Watch 3 NOT polled.
        """
        from vigil.ik_client import IKAPIAuthError
        from vigil.polling import poll_cycle

        watches = [_make_watch(f"Watch {i}") for i in range(3)]
        patch_supabase.table.return_value.execute.return_value = MagicMock(data=watches)

        call_count = 0

        async def mock_poll_single(watch):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise IKAPIAuthError("403 Forbidden")
            return []

        with patch("vigil.polling.poll_single_watch", side_effect=mock_poll_single):
            await poll_cycle()

        # Watch 3 should NOT have been polled (halted after 403)
        assert call_count == 2

    async def test_notification_retry_cycle(
        self, patch_supabase, test_settings, mock_smtp
    ):
        """
        Failed notification → not marked notified → succeeds next cycle.
        """
        from vigil.notifier import dispatch_pending_notifications

        test_settings.notification_email_enabled = True
        test_settings.notification_email_recipients = "a@b.com"

        match_with_retry = {
            "id": "m1",
            "watch_id": "w1",
            "judgment_id": "j1",
            "is_notified": False,
            "retry_count": 1,
            "judgments": {
                "title": "Test Judgment",
                "court": "Delhi HC",
                "ik_url": "https://indiankanoon.org/doc/123/",
            },
        }

        # First dispatch — email fails
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[match_with_retry]),  # fetch unnotified
            MagicMock(data=[{"id": "w1", "name": "Test Watch"}]),  # fetch watch names
        ]
        mock_smtp.send_message.side_effect = Exception("SMTP error")
        await dispatch_pending_notifications()

        # No is_notified update should have happened
        update_calls_after_fail = (
            patch_supabase.table.return_value.update.call_args_list
        )
        notified_updates = [
            c for c in update_calls_after_fail if "is_notified" in str(c)
        ]
        assert len(notified_updates) == 0

        # Second dispatch — email succeeds
        patch_supabase.table.return_value.update.reset_mock()
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[match_with_retry]),  # fetch unnotified
            MagicMock(data=[{"id": "w1", "name": "Test Watch"}]),  # fetch watch names
            MagicMock(data=[{}]),  # update is_notified
        ]
        mock_smtp.send_message.side_effect = None
        await dispatch_pending_notifications()

        update_calls = patch_supabase.table.return_value.update.call_args_list
        assert any("is_notified" in str(c) for c in update_calls)

    async def test_daily_digest_aggregation(
        self, patch_supabase, test_settings, mock_smtp
    ):
        """
        10 matches across 3 watches in past 24h → 3 digest emails (one per watch).
        """
        from vigil.notifier import send_daily_digest

        test_settings.daily_digest_enabled = True
        test_settings.notification_email_recipients = "a@b.com"

        matches = []
        for i in range(10):
            watch_idx = i % 3
            matches.append(
                {
                    "id": f"m{i}",
                    "watch_id": f"w{watch_idx}",
                    "judgment_id": f"j{i}",
                    "matched_at": datetime.now(timezone.utc).isoformat(),
                    "judgments": {
                        "title": f"Judgment {i}",
                        "court": "Delhi HC",
                        "ik_url": f"https://indiankanoon.org/doc/{i}/",
                    },
                }
            )

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=matches),  # fetch matches from past 24h
            MagicMock(
                data=[
                    {"id": "w0", "name": "Watch 0"},
                    {"id": "w1", "name": "Watch 1"},
                    {"id": "w2", "name": "Watch 2"},
                ]
            ),  # fetch watch names
        ]

        await send_daily_digest()

        # 3 watch groups → 3 digest emails
        assert mock_smtp.send_message.call_count == 3
