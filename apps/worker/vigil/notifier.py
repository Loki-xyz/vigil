"""
Notification dispatch.

RULES:
1. Batch by watch — one email per watch, not per judgment.
2. On success: set is_notified=TRUE.
3. On failure: log error, DO NOT set is_notified. Retry next cycle (max 3).
4. Daily digest: summary of all matches from past 24h.

EMAIL SUBJECT: "[Vigil] {watch_name}: {count} new judgment(s)"
SLACK: Block Kit formatted with linked titles, court, date.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import aiosmtplib
import httpx

from vigil.config import settings
from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)


async def send_email_alert(
    watch_name: str, matches: list[dict], recipients: list[str]
) -> bool:
    """
    Send email alert for new matches on a watch.

    Returns True on success, False on failure.
    """
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Vigil] {watch_name}: {len(matches)} new judgment(s)"
        msg["From"] = settings.smtp_from_email
        msg["To"] = ", ".join(recipients)

        body_lines = [
            "Vigil — Judgment Alert",
            f"Watch: {watch_name}",
            f"{len(matches)} new judgment(s) matched",
            "",
            "=" * 40,
            "",
        ]
        for i, match in enumerate(matches, 1):
            j = match.get("judgments", {})
            body_lines.extend([
                f"  {i}. {j.get('title', 'Unknown')}",
                f"     Court: {j.get('court', 'Unknown')}",
                f"     Link:  {j.get('ik_url', '')}",
                "",
            ])
        body_lines.extend(["=" * 40, "", "Vigil · Trilegal Internal Tool"])
        msg.set_content("\n".join(body_lines))

        smtp = aiosmtplib.SMTP(hostname=settings.smtp_host, port=settings.smtp_port)
        await smtp.connect()
        if settings.smtp_use_tls:
            await smtp.starttls()
        await smtp.login(settings.smtp_username, settings.smtp_password)
        await smtp.send_message(msg)
        await smtp.quit()

        logger.info("Email sent for %s to %s", watch_name, recipients)
        return True

    except Exception:
        logger.error("Email alert failed for %s", watch_name, exc_info=True)
        return False


async def send_slack_alert(
    watch_name: str, matches: list[dict], webhook_url: str
) -> bool:
    """
    Send Slack Block Kit message for new matches on a watch.

    Returns True on success, False on failure.
    """
    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Vigil: {watch_name} — {len(matches)} new judgment(s)",
                },
            },
            {"type": "divider"},
        ]
        for match in matches:
            j = match.get("judgments", {})
            title = j.get("title", "Unknown")
            url = j.get("ik_url", "")
            court = j.get("court", "Unknown")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{url}|{title}>*\n{court}",
                },
            })
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Vigil · Trilegal Internal"}
            ],
        })

        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json={"blocks": blocks})
            if resp.is_success:
                logger.info("Slack alert sent for %s", watch_name)
                return True
            logger.error("Slack returned %s for %s", resp.status_code, watch_name)
            return False

    except Exception:
        logger.error("Slack alert failed for %s", watch_name, exc_info=True)
        return False


async def send_admin_alert(subject: str, message: str) -> None:
    """Send critical admin alert via all configured channels.

    Used for CRITICAL errors like IK API 403 (auth failure).
    Best-effort: logs failures but never raises.
    """
    email_recipients = [
        e.strip()
        for e in settings.notification_email_recipients.split(",")
        if e.strip()
    ]

    if email_recipients:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[Vigil CRITICAL] {subject}"
            msg["From"] = settings.smtp_from_email
            msg["To"] = ", ".join(email_recipients)
            msg.set_content(
                f"CRITICAL ALERT\n\n{message}\n\n"
                "Action required: Check IK API token and restart worker.\n\n"
                "Vigil · Trilegal Internal Tool"
            )
            smtp = aiosmtplib.SMTP(hostname=settings.smtp_host, port=settings.smtp_port)
            await smtp.connect()
            if settings.smtp_use_tls:
                await smtp.starttls()
            await smtp.login(settings.smtp_username, settings.smtp_password)
            await smtp.send_message(msg)
            await smtp.quit()
            logger.info("Admin alert email sent: %s", subject)
        except Exception:
            logger.error("Failed to send admin alert email", exc_info=True)

    slack_webhook = settings.slack_webhook_url
    if slack_webhook:
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f":rotating_light: CRITICAL: {subject}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "Vigil Admin Alert · Immediate action required"}
                    ],
                },
            ]
            async with httpx.AsyncClient() as client:
                resp = await client.post(slack_webhook, json={"blocks": blocks})
                if resp.is_success:
                    logger.info("Admin alert Slack sent: %s", subject)
                else:
                    logger.error("Admin alert Slack failed: %s", resp.status_code)
        except Exception:
            logger.error("Failed to send admin alert Slack", exc_info=True)


async def dispatch_pending_notifications() -> None:
    """
    Fetch all un-notified matches, group by watch, and dispatch alerts.
    """
    # Fetch un-notified matches with judgment data
    resp = (
        supabase.table("watch_matches")
        .select("*, judgments(*)")
        .eq("is_notified", False)
        .execute()
    )
    matches = resp.data or []

    # Filter out exhausted retries
    matches = [m for m in matches if m.get("retry_count", 0) < 3]
    if not matches:
        return

    # Group by watch_id
    by_watch: dict[str, list[dict]] = {}
    for m in matches:
        by_watch.setdefault(m["watch_id"], []).append(m)

    # Fetch watch names
    watch_ids = list(by_watch.keys())
    watch_resp = (
        supabase.table("watches")
        .select("id, name")
        .in_("id", watch_ids)
        .execute()
    )
    watch_names = {w["id"]: w["name"] for w in (watch_resp.data or [])}

    # Read channel config from settings
    email_enabled = settings.notification_email_enabled
    slack_enabled = settings.notification_slack_enabled
    email_recipients = [
        e.strip()
        for e in settings.notification_email_recipients.split(",")
        if e.strip()
    ]
    slack_webhook = settings.slack_webhook_url

    for watch_id, group in by_watch.items():
        watch_name = watch_names.get(watch_id, "Unknown Watch")
        match_ids = [m["id"] for m in group]
        success = False

        if email_enabled and email_recipients:
            success = await send_email_alert(watch_name, group, email_recipients)

        if slack_enabled and slack_webhook:
            slack_ok = await send_slack_alert(watch_name, group, slack_webhook)
            success = success or slack_ok

        if success:
            (
                supabase.table("watch_matches")
                .update({
                    "is_notified": True,
                    "notified_at": datetime.now(timezone.utc).isoformat(),
                })
                .in_("id", match_ids)
                .execute()
            )
            logger.info("Marked %d matches notified for %s", len(match_ids), watch_name)
        else:
            # Increment retry_count for failed notifications
            for match in group:
                try:
                    (
                        supabase.table("watch_matches")
                        .update({"retry_count": match.get("retry_count", 0) + 1})
                        .eq("id", match["id"])
                        .execute()
                    )
                except Exception:
                    logger.error(
                        "Failed to increment retry_count for match %s",
                        match["id"],
                        exc_info=True,
                    )
            logger.warning(
                "Notification failed for %s (%d matches). retry_count incremented.",
                watch_name,
                len(group),
            )


async def send_daily_digest() -> None:
    """Send summary of all matches from past 24h. Triggered at 09:00 IST."""
    if not settings.daily_digest_enabled:
        return

    email_recipients = [
        e.strip()
        for e in settings.notification_email_recipients.split(",")
        if e.strip()
    ]
    if not email_recipients:
        return

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    resp = (
        supabase.table("watch_matches")
        .select("*, judgments(*)")
        .gte("matched_at", since)
        .execute()
    )
    matches = resp.data or []
    if not matches:
        return

    # Group by watch_id
    by_watch: dict[str, list[dict]] = {}
    for m in matches:
        by_watch.setdefault(m["watch_id"], []).append(m)

    watch_ids = list(by_watch.keys())
    watch_resp = (
        supabase.table("watches")
        .select("id, name")
        .in_("id", watch_ids)
        .execute()
    )
    watch_names = {w["id"]: w["name"] for w in (watch_resp.data or [])}

    for watch_id, group in by_watch.items():
        watch_name = watch_names.get(watch_id, "Unknown Watch")
        await send_email_alert(f"Daily Digest: {watch_name}", group, email_recipients)
