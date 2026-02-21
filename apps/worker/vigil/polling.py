"""
Polling engine.

FLOW PER CYCLE:
1. Fetch active watches from Supabase where interval has elapsed.
2. For each watch:
   a. Build query -> call IK search -> process results via matcher.
   b. Update last_polled_at.
3. Trigger notification dispatch for pending matches.

SC SCRAPE CYCLE (separate schedule):
1. Fetch all active watches with 'supremecourt' in court_filter.
2. Scrape SC daily orders (single scrape, shared across all watches).
3. Two-phase matching: fast on parties, then selective PDF download.
4. Create judgments + watch_matches for confirmed matches.

ERROR HANDLING:
- Single watch failure -> log and continue. Never halt the cycle.
- IK API 403 -> PAUSE ALL polling. Admin alert.
- IK API 5xx/timeout -> exponential backoff for that watch.
- SC scraper: circuit breaker after 3 consecutive failures.

SCHEDULING:
- APScheduler AsyncIOScheduler
- Main cycle: every 30 minutes (only polls watches whose interval has elapsed)
- Notification dispatch: every 10 minutes
- Poll requests: every 30 seconds (check for "Poll Now" requests)
- Daily digest: 9:00 AM IST
- SC scrape: configurable CronTrigger hours (default 8 AM + 5 PM IST)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from vigil.config import settings
from vigil.ik_client import IKAPIAuthError, IKAPIRateLimitError, IKClient
from vigil.matcher import process_sc_orders, process_search_results
from vigil.notifier import dispatch_pending_notifications, send_admin_alert, send_daily_digest
from vigil.query_builder import build_query
from vigil.sc_client import SCClient, SCCaptchaError, SCPDFDownloadError, SCScraperError
from vigil.sc_matcher import match_order_against_watch, needs_pdf_download
from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)

_ik_client: IKClient | None = None
_sc_client: SCClient | None = None

# In-memory backoff tracking for 429 rate limits.
# Maps watch_id -> datetime when backoff expires.
# Lost on restart — acceptable since rate limits are temporary.
_watch_backoffs: dict[str, datetime] = {}

# Circuit breaker for SC scraper — counts consecutive failures.
_sc_consecutive_failures: int = 0
_SC_MAX_CONSECUTIVE_FAILURES = 3


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


def _get_sc_client() -> SCClient:
    """Lazy-init the shared SC website scraper client."""
    global _sc_client
    if _sc_client is None:
        _sc_client = SCClient(
            base_url=settings.sc_base_url,
            timeout=settings.sc_request_timeout_seconds,
            max_retries=settings.sc_max_retries,
            rate_limit_seconds=settings.sc_rate_limit_seconds,
            captcha_max_attempts=settings.sc_captcha_max_attempts,
        )
    return _sc_client


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

        if last_polled_str:
            from_date = datetime.fromisoformat(last_polled_str).date()
        else:
            # First poll: look back N days to catch recent judgments
            from_date = (
                datetime.now(timezone.utc) - timedelta(days=settings.first_poll_lookback_days)
            ).date()

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
    # Clean up stale "processing" requests (worker crashed or hung)
    try:
        stale_cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        stale_resp = (
            supabase.table("poll_requests")
            .update({"status": "failed"})
            .eq("status", "processing")
            .lt("created_at", stale_cutoff)
            .execute()
        )
        if stale_resp.data:
            logger.warning(
                "Marked %d stale poll request(s) as failed",
                len(stale_resp.data),
            )
    except Exception:
        logger.error("Failed to clean up stale poll requests", exc_info=True)

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
            court_filter = watch.get("court_filter") or []
            is_sc = "supremecourt" in court_filter

            # SC watches: use scraper instead of IK API (more reliable, no cost)
            if is_sc and settings.sc_scraper_enabled:
                sc_matches = await sc_scrape_for_watch(watch)
                logger.info(
                    "Poll Now SC scrape for watch %s found %d matches",
                    watch["id"], len(sc_matches),
                )
            else:
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


async def sc_scrape_cycle() -> None:
    """
    Scrape SC daily orders and match against all active Supreme Court watches.

    Runs on a separate schedule (default 8 AM + 5 PM IST).
    Single scrape shared across all SC watches, then two-phase matching.
    """
    global _sc_consecutive_failures

    if not settings.sc_scraper_enabled:
        logger.info("SC scraper disabled. Skipping.")
        return

    try:
        # 1. Get all SC watches
        resp = (
            supabase.table("watches")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        all_watches = resp.data or []
        sc_watches = [
            w for w in all_watches
            if "supremecourt" in (w.get("court_filter") or [])
        ]

        if not sc_watches:
            logger.info("No active watches with supremecourt filter. Skipping SC scrape.")
            return

        # 2. Scrape orders (single call, shared across all watches)
        client = _get_sc_client()
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=settings.sc_lookback_days)
        ).date()
        to_date = datetime.now(timezone.utc).date()

        orders = await client.fetch_daily_orders(from_date, to_date)
        logger.info(
            "SC scraper fetched %d daily orders for %s to %s",
            len(orders), from_date, to_date,
        )

        if not orders:
            _sc_consecutive_failures = 0
            return

        # 3. Two-phase matching
        for order in orders:
            # Phase 1: Fast match against parties/case_number
            matching_watches_phase1: list[tuple] = []
            watches_needing_pdf: list[dict] = []

            for watch in sc_watches:
                result = match_order_against_watch(order, watch, full_text=None)
                if result.is_match:
                    matching_watches_phase1.append((watch, result))
                elif needs_pdf_download(order, [watch]):
                    watches_needing_pdf.append(watch)

            # Phase 2: Download PDF if any watch needs it
            full_text: str | None = None
            if watches_needing_pdf and settings.sc_pdf_download_enabled:
                try:
                    full_text = await client.download_and_parse_pdf(order.pdf_url)
                except SCPDFDownloadError:
                    logger.warning(
                        "Failed to download PDF for %s", order.case_number
                    )

            # Re-match watches that needed PDF
            matching_watches_phase2: list[tuple] = []
            if full_text:
                for watch in watches_needing_pdf:
                    result = match_order_against_watch(
                        order, watch, full_text=full_text
                    )
                    if result.is_match:
                        matching_watches_phase2.append((watch, result))

            # 4. Process all matches
            all_matches = matching_watches_phase1 + matching_watches_phase2
            for watch, match_result in all_matches:
                try:
                    await process_sc_orders(
                        watch["id"],
                        [(order, match_result, full_text or "")],
                    )
                except Exception:
                    logger.error(
                        "Error processing SC order %s for watch %s",
                        order.case_number, watch["id"],
                        exc_info=True,
                    )

        _sc_consecutive_failures = 0

        try:
            await dispatch_pending_notifications()
        except Exception:
            logger.error("Error dispatching notifications after SC scrape", exc_info=True)

    except SCCaptchaError:
        _sc_consecutive_failures += 1
        logger.error("SC captcha solving failed after retries", exc_info=True)
        if _sc_consecutive_failures >= _SC_MAX_CONSECUTIVE_FAILURES:
            logger.critical(
                "SC scraper failed %d consecutive times. Sending admin alert.",
                _sc_consecutive_failures,
            )
            try:
                await send_admin_alert(
                    "SC Website Scraper Failures",
                    f"The SC website scraper has failed {_sc_consecutive_failures} "
                    "consecutive times. Captcha solving is failing.\n\n"
                    "SC scraping will continue to retry on schedule.",
                )
            except Exception:
                logger.error("Failed to send admin alert for SC failures", exc_info=True)
    except SCScraperError:
        _sc_consecutive_failures += 1
        logger.error("SC website scraping failed", exc_info=True)
        if _sc_consecutive_failures >= _SC_MAX_CONSECUTIVE_FAILURES:
            try:
                await send_admin_alert(
                    "SC Website Scraper Failures",
                    f"The SC website scraper has failed {_sc_consecutive_failures} "
                    "consecutive times. The website may have changed structure.\n\n"
                    "SC scraping will continue to retry on schedule.",
                )
            except Exception:
                logger.error("Failed to send admin alert for SC failures", exc_info=True)
    except Exception:
        _sc_consecutive_failures += 1
        logger.error("Unexpected error in SC scrape cycle", exc_info=True)


async def _sc_scrape_for_watch_inner(watch: dict) -> list[dict]:
    """Inner implementation of SC scrape for a single watch (no timeout wrapper)."""
    client = _get_sc_client()
    from_date = (
        datetime.now(timezone.utc) - timedelta(days=settings.sc_lookback_days)
    ).date()
    to_date = datetime.now(timezone.utc).date()

    orders = await client.fetch_daily_orders(
        from_date, to_date, watch_id=watch["id"],
    )
    logger.info(
        "Poll Now SC scrape for watch %s fetched %d orders (%s to %s)",
        watch["id"], len(orders), from_date, to_date,
    )

    if not orders:
        return []

    all_new_matches: list[dict] = []

    for order in orders:
        # Phase 1: Fast match on parties/case_number (no PDF)
        result = match_order_against_watch(order, watch, full_text=None)
        if result.is_match:
            try:
                matches = await process_sc_orders(
                    watch["id"], [(order, result, "")],
                )
                all_new_matches.extend(matches)
            except Exception:
                logger.error(
                    "Error processing SC order %s for watch %s",
                    order.case_number, watch["id"], exc_info=True,
                )
            continue

        # Phase 2: Download PDF if needed and re-match
        if needs_pdf_download(order, [watch]) and settings.sc_pdf_download_enabled:
            full_text: str | None = None
            try:
                full_text = await client.download_and_parse_pdf(order.pdf_url)
            except SCPDFDownloadError:
                logger.warning(
                    "Failed to download PDF for %s", order.case_number,
                )

            if full_text:
                result = match_order_against_watch(order, watch, full_text=full_text)
                if result.is_match:
                    try:
                        matches = await process_sc_orders(
                            watch["id"], [(order, result, full_text)],
                        )
                        all_new_matches.extend(matches)
                    except Exception:
                        logger.error(
                            "Error processing SC order %s for watch %s",
                            order.case_number, watch["id"], exc_info=True,
                        )

    return all_new_matches


async def sc_scrape_for_watch(watch: dict) -> list[dict]:
    """
    Run SC website scrape and two-phase matching for a single watch.

    Used by check_poll_requests() for user-initiated "Poll Now" on SC watches.
    Does NOT modify _sc_consecutive_failures (user-initiated, not scheduled).
    Does NOT call dispatch_pending_notifications (the 10-min job handles that).

    Returns list of newly created watch_match dicts. Returns [] on any error.
    Enforces a 3-minute overall timeout to prevent hanging.
    """
    try:
        return await asyncio.wait_for(
            _sc_scrape_for_watch_inner(watch),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        logger.error(
            "SC scrape for Poll Now watch %s timed out after 180s",
            watch.get("id"),
        )
        return []
    except (SCCaptchaError, SCScraperError):
        logger.error(
            "SC scrape failed for Poll Now watch %s", watch.get("id"), exc_info=True,
        )
        return []
    except Exception:
        logger.error(
            "Unexpected error in SC scrape for watch %s", watch.get("id"), exc_info=True,
        )
        return []


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

    # SC scrape jobs (e.g., 8 AM and 5 PM IST)
    if settings.sc_scraper_enabled:
        for hour_str in settings.sc_scrape_schedule_hours.split(","):
            hour = int(hour_str.strip())
            scheduler.add_job(
                sc_scrape_cycle,
                CronTrigger(
                    hour=hour,
                    minute=0,
                    timezone=ZoneInfo(settings.timezone),
                ),
                id=f"sc_scrape_{hour}",
                name=f"sc_scrape_{hour}",
            )

    return scheduler
