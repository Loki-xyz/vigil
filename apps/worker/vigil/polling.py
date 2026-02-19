"""
Polling engine.

FLOW PER CYCLE:
1. Fetch active watches from Supabase where interval has elapsed.
2. For each watch:
   a. Build query -> call IK search -> process results via matcher.
   b. Update last_polled_at.
3. Trigger notification dispatch for pending matches.

ERROR HANDLING:
- Single watch failure -> log and continue. Never halt the cycle.
- IK API 403 -> PAUSE ALL polling. Admin alert.
- IK API 5xx/timeout -> exponential backoff for that watch.

SCHEDULING:
- APScheduler AsyncIOScheduler
- Main cycle: every 30 minutes (only polls watches whose interval has elapsed)
- Notification dispatch: every 10 minutes
- Poll requests: every 30 seconds (check for "Poll Now" requests)
- Daily digest: 9:00 AM IST
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from vigil.config import settings
from vigil.ik_client import IKAPIAuthError, IKAPIRateLimitError, IKClient
from vigil.matcher import process_search_results
from vigil.notifier import dispatch_pending_notifications, send_admin_alert, send_daily_digest
from vigil.query_builder import build_query
from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)

_ik_client: IKClient | None = None

# In-memory backoff tracking for 429 rate limits.
# Maps watch_id -> datetime when backoff expires.
# Lost on restart — acceptable since rate limits are temporary.
_watch_backoffs: dict[str, datetime] = {}


def _get_ik_client() -> IKClient:
    """Lazy-init the shared IK API client."""
    global _ik_client
    if _ik_client is None:
        _ik_client = IKClient(
            base_url=settings.ik_api_base_url,
            token=settings.ik_api_token,
            timeout=settings.ik_api_timeout_seconds,
            max_retries=settings.ik_api_max_retries,
        )
    return _ik_client


def _is_due(watch: dict) -> bool:
    """Check if a watch's polling interval has elapsed and not in backoff."""
    watch_id = watch.get("id")

    # Check rate-limit backoff
    if watch_id in _watch_backoffs:
        if datetime.now(timezone.utc) < _watch_backoffs[watch_id]:
            return False
        else:
            del _watch_backoffs[watch_id]

    last_polled_str = watch.get("last_polled_at")
    if not last_polled_str:
        return True
    last_polled = datetime.fromisoformat(last_polled_str)
    interval_min = watch.get("polling_interval_minutes", 30)
    return datetime.now(timezone.utc) - last_polled >= timedelta(minutes=interval_min)


async def poll_single_watch(watch: dict) -> list[dict]:
    """Poll a single watch and return new matches."""
    try:
        last_polled_str = watch.get("last_polled_at")
        created_str = watch.get("created_at")
        from_dt_str = last_polled_str or created_str

        if from_dt_str:
            from_date = datetime.fromisoformat(from_dt_str).date()
        else:
            from_date = datetime.now(timezone.utc).date()

        query = build_query(
            watch["watch_type"],
            watch["query_terms"],
            watch.get("court_filter") or [],
            from_date,
        )

        client = _get_ik_client()
        response = await client.search(query, watch_id=watch["id"])
        docs = response.get("docs", [])

        matches = await process_search_results(watch["id"], docs)

        try:
            supabase.table("watches").update({
                "last_polled_at": datetime.now(timezone.utc).isoformat(),
                "last_poll_result_count": len(docs),
            }).eq("id", watch["id"]).execute()
        except Exception:
            logger.error(
                "Failed to update last_polled_at for watch %s",
                watch.get("id"),
                exc_info=True,
            )

        return matches

    except IKAPIAuthError:
        raise
    except IKAPIRateLimitError:
        watch_id = watch.get("id")
        interval = watch.get("polling_interval_minutes", 30)
        backoff_until = datetime.now(timezone.utc) + timedelta(minutes=interval * 2)
        _watch_backoffs[watch_id] = backoff_until
        logger.warning(
            "Rate limited (429) for watch %s. Backing off until %s (doubled interval: %d min)",
            watch_id,
            backoff_until.isoformat(),
            interval * 2,
        )
        return []
    except Exception:
        logger.error(
            "Error polling watch %s", watch.get("id"), exc_info=True
        )
        return []


async def poll_cycle() -> None:
    """Execute one full polling cycle across all active watches."""
    if not settings.polling_enabled:
        logger.info("Polling disabled (VIGIL_POLLING_ENABLED=false). Skipping cycle.")
        return

    try:
        resp = (
            supabase.table("watches")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        watches = resp.data or []
    except Exception:
        logger.error(
            "Failed to fetch watches from Supabase. Will retry next cycle.",
            exc_info=True,
        )
        return

    due_watches = [w for w in watches if _is_due(w)]

    for watch in due_watches:
        try:
            await poll_single_watch(watch)
        except IKAPIAuthError:
            logger.critical("IK API auth error (403) — halting ALL polling. Sending admin alert.")
            try:
                await send_admin_alert(
                    "IK API Authentication Failure (403)",
                    "The Indian Kanoon API returned a 403 Forbidden error.\n"
                    "ALL polling has been paused.\n\n"
                    "Please verify the API token (VIGIL_IK_API_TOKEN) and restart the worker.",
                )
            except Exception:
                logger.error("Failed to send admin alert for 403", exc_info=True)
            break
        except Exception:
            logger.error(
                "Error polling watch %s", watch.get("id"), exc_info=True
            )
            continue

    try:
        await dispatch_pending_notifications()
    except Exception:
        logger.error("Error dispatching notifications", exc_info=True)


async def check_poll_requests() -> None:
    """Check poll_requests table for pending 'Poll Now' requests."""
    resp = (
        supabase.table("poll_requests")
        .select("*")
        .eq("status", "pending")
        .execute()
    )
    requests = resp.data or []

    for req in requests:
        try:
            # Mark as processing
            supabase.table("poll_requests").update(
                {"status": "processing"}
            ).eq("id", req["id"]).execute()

            # Fetch the watch
            watch_resp = (
                supabase.table("watches")
                .select("*")
                .eq("id", req["watch_id"])
                .single()
                .execute()
            )
            watch = watch_resp.data

            await poll_single_watch(watch)

            # Mark as done
            supabase.table("poll_requests").update(
                {"status": "done"}
            ).eq("id", req["id"]).execute()

        except Exception:
            logger.error(
                "Error processing poll request %s",
                req.get("id"),
                exc_info=True,
            )
            try:
                supabase.table("poll_requests").update(
                    {"status": "failed"}
                ).eq("id", req["id"]).execute()
            except Exception:
                logger.error(
                    "Failed to update poll request status", exc_info=True
                )


def setup_scheduler() -> AsyncIOScheduler:
    """Configure and return the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        poll_cycle,
        IntervalTrigger(minutes=30),
        id="poll_cycle",
        name="poll_cycle",
    )

    scheduler.add_job(
        dispatch_pending_notifications,
        IntervalTrigger(minutes=10),
        id="dispatch_pending_notifications",
        name="dispatch_pending_notifications",
    )

    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=9, minute=0, timezone=ZoneInfo(settings.timezone)),
        id="send_daily_digest",
        name="send_daily_digest",
    )

    scheduler.add_job(
        check_poll_requests,
        IntervalTrigger(seconds=30),
        id="check_poll_requests",
        name="check_poll_requests",
    )

    return scheduler
