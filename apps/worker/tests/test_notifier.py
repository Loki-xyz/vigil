"""Tests for vigil/notifier.py — email, dispatch, and daily digest."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------
SAMPLE_MATCHES = [
    {
        "id": "m1",
        "watch_id": "w1",
        "judgment_id": "j1",
        "matched_at": "2026-02-17T12:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...cloud computing...",
        "judgments": {
            "title": "AWS vs CIT",
            "court": "Delhi HC",
            "ik_url": "https://indiankanoon.org/doc/123/",
        },
    },
]

SAMPLE_MATCHES_MULTI = [
    {
        "id": "m1",
        "watch_id": "w1",
        "judgment_id": "j1",
        "matched_at": "2026-02-17T12:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...cloud computing...",
        "judgments": {
            "title": "AWS vs CIT",
            "court": "Delhi HC",
            "ik_url": "https://indiankanoon.org/doc/123/",
        },
    },
    {
        "id": "m2",
        "watch_id": "w1",
        "judgment_id": "j2",
        "matched_at": "2026-02-17T13:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...data protection...",
        "judgments": {
            "title": "Google vs DPIIT",
            "court": "Supreme Court of India",
            "ik_url": "https://indiankanoon.org/doc/456/",
        },
    },
    {
        "id": "m3",
        "watch_id": "w2",
        "judgment_id": "j3",
        "matched_at": "2026-02-17T14:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...trademark infringement...",
        "judgments": {
            "title": "Nike vs Counterfeit Ltd",
            "court": "Bombay HC",
            "ik_url": "https://indiankanoon.org/doc/789/",
        },
    },
]

SAMPLE_MATCHES_FIVE = SAMPLE_MATCHES_MULTI + [
    {
        "id": "m4",
        "watch_id": "w1",
        "judgment_id": "j4",
        "matched_at": "2026-02-18T09:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...antitrust...",
        "judgments": {
            "title": "CCI vs Mega Corp",
            "court": "NCLAT",
            "ik_url": "https://indiankanoon.org/doc/1010/",
        },
    },
    {
        "id": "m5",
        "watch_id": "w2",
        "judgment_id": "j5",
        "matched_at": "2026-02-18T10:00:00Z",
        "is_notified": False,
        "retry_count": 0,
        "snippet": "...patent validity...",
        "judgments": {
            "title": "Pharma Inc vs Generic Co",
            "court": "Delhi HC",
            "ik_url": "https://indiankanoon.org/doc/2020/",
        },
    },
]


# ============================================================================
# EMAIL TESTS
# ============================================================================


# ---------------------------------------------------------------------------
# 1. Email success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_success(mock_smtp, test_settings):
    """Returns True, SMTP connect/login/send/quit called."""
    from vigil.notifier import send_email_alert

    result = await send_email_alert("AWS Watch", SAMPLE_MATCHES, ["user@example.com"])

    assert result is True
    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Email subject format
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_subject_format(mock_smtp, test_settings):
    """Subject line: '[Vigil] AWS Watch: 3 new judgment(s)'."""
    from vigil.notifier import send_email_alert

    three_matches = SAMPLE_MATCHES_MULTI
    await send_email_alert("AWS Watch", three_matches, ["user@example.com"])

    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert sent_msg["Subject"] == "[Vigil] AWS Watch: 3 new judgment(s)"


# ---------------------------------------------------------------------------
# 3. Email body contains details
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_body_contains_details(mock_smtp, test_settings):
    """Body has title, court, IK URL."""
    from vigil.notifier import send_email_alert

    await send_email_alert("AWS Watch", SAMPLE_MATCHES, ["user@example.com"])

    sent_msg = mock_smtp.send_message.call_args[0][0]
    body = (
        sent_msg.get_body().get_content()
        if hasattr(sent_msg, "get_body")
        else str(sent_msg)
    )

    assert "AWS vs CIT" in body
    assert "Delhi HC" in body
    assert "https://indiankanoon.org/doc/123/" in body


# ---------------------------------------------------------------------------
# 4. Email multiple recipients
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_multiple_recipients(mock_smtp, test_settings):
    """2 recipients -> both in message."""
    from vigil.notifier import send_email_alert

    recipients = ["alice@example.com", "bob@example.com"]
    await send_email_alert("AWS Watch", SAMPLE_MATCHES, recipients)

    sent_msg = mock_smtp.send_message.call_args[0][0]
    to_header = sent_msg["To"]

    assert "alice@example.com" in to_header
    assert "bob@example.com" in to_header


# ---------------------------------------------------------------------------
# 5. Email failure returns False
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_failure_returns_false(mock_smtp, test_settings):
    """SMTP raises -> returns False."""
    from vigil.notifier import send_email_alert

    mock_smtp.send_message.side_effect = Exception("SMTP connection refused")

    result = await send_email_alert("AWS Watch", SAMPLE_MATCHES, ["user@example.com"])

    assert result is False


# ---------------------------------------------------------------------------
# 6. Email TLS enabled
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_tls_enabled(mock_smtp, test_settings):
    """smtp_use_tls=True -> starttls() called."""
    from vigil.notifier import send_email_alert

    test_settings.smtp_use_tls = True

    await send_email_alert("AWS Watch", SAMPLE_MATCHES, ["user@example.com"])

    mock_smtp.starttls.assert_called_once()


# ---------------------------------------------------------------------------
# 7. Email no TLS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_email_no_tls(mock_smtp, test_settings):
    """smtp_use_tls=False -> starttls() NOT called."""
    from vigil.notifier import send_email_alert

    test_settings.smtp_use_tls = False

    await send_email_alert("AWS Watch", SAMPLE_MATCHES, ["user@example.com"])

    mock_smtp.starttls.assert_not_called()


# ============================================================================
# DISPATCH TESTS
# ============================================================================


# ---------------------------------------------------------------------------
# 8. Dispatch fetches unnotified
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_fetches_unnotified(
    patch_supabase, mock_supabase, test_settings
):
    """Selects where is_notified=False."""
    from vigil.notifier import dispatch_pending_notifications

    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    await dispatch_pending_notifications()

    # Verify the query filters by is_notified=False
    mock_supabase.table.assert_any_call("watch_matches")
    eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
    found = any(c[0] == ("is_notified", False) for c in eq_calls)
    assert found, "Should query for is_notified=False"


# ---------------------------------------------------------------------------
# 9. Dispatch groups by watch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_groups_by_watch(patch_supabase, mock_supabase, test_settings):
    """3 matches for 2 watches -> 2 send calls."""
    from vigil.notifier import dispatch_pending_notifications

    test_settings.notification_email_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    # Use side_effect to return different data for successive .execute() calls
    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES_MULTI),  # watch_matches query
        MagicMock(
            data=[  # watches query
                {"id": "w1", "name": "AWS Watch"},
                {"id": "w2", "name": "IP Watch"},
            ]
        ),
        MagicMock(data=[]),  # update for w1
        MagicMock(data=[]),  # update for w2
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=True
    ) as mock_send:
        await dispatch_pending_notifications()

        assert mock_send.call_count == 2


# ---------------------------------------------------------------------------
# 10. Dispatch marks notified on success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_marks_notified_on_success(
    patch_supabase, mock_supabase, test_settings
):
    """Sets is_notified=True, notified_at."""
    from vigil.notifier import dispatch_pending_notifications

    test_settings.notification_email_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES),  # watch_matches query
        MagicMock(data=[{"id": "w1", "name": "AWS Watch"}]),  # watches query
        MagicMock(data=[]),  # update
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=True
    ):
        await dispatch_pending_notifications()

    # Verify update was called with is_notified=True
    update_calls = mock_supabase.table.return_value.update.call_args_list
    found_update = any("is_notified" in str(c) for c in update_calls)
    assert found_update or mock_supabase.table.return_value.update.called


# ---------------------------------------------------------------------------
# 11. Dispatch no mark on failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_no_mark_on_failure(
    patch_supabase, mock_supabase, test_settings
):
    """Email fails -> is_notified stays False."""
    from vigil.notifier import dispatch_pending_notifications

    test_settings.notification_email_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES),  # watch_matches query
        MagicMock(data=[{"id": "w1", "name": "AWS Watch"}]),  # watches query
        MagicMock(data=[{}]),  # retry_count update
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=False
    ):
        await dispatch_pending_notifications()

    # Update to is_notified=True should NOT have been called
    update_calls = mock_supabase.table.return_value.update.call_args_list
    notified_true_calls = [
        c
        for c in update_calls
        if any("is_notified" in str(arg) and "True" in str(arg) for arg in c)
    ]
    assert len(notified_true_calls) == 0


# ---------------------------------------------------------------------------
# 12. Dispatch retry_count >= 3 filtered by query
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_max_3_retries(patch_supabase, mock_supabase, test_settings):
    """retry_count >= 3 is now filtered server-side via .lt('retry_count', 3).

    Verify the query includes the lt filter. Since the mock's chainable
    table mock returns empty by default, dispatch exits early with no sends.
    """
    from vigil.notifier import dispatch_pending_notifications

    # The chainable mock already returns data=[] by default for execute(),
    # so dispatch should exit after the query returns empty (the DB filtered
    # out retry_count >= 3 rows).
    with patch("vigil.notifier.send_email_alert", new_callable=AsyncMock) as mock_send:
        await dispatch_pending_notifications()

        mock_send.assert_not_called()

    # Verify the lt filter was applied
    lt_calls = mock_supabase.table.return_value.lt.call_args_list
    found_lt = any(c[0] == ("retry_count", 3) for c in lt_calls)
    assert found_lt, "Should filter retry_count < 3 in the Supabase query"


# ---------------------------------------------------------------------------
# 13. Dispatch respects email settings
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_respects_settings(patch_supabase, mock_supabase, test_settings):
    """email_enabled=true, recipients set -> email sent."""
    from vigil.notifier import dispatch_pending_notifications

    test_settings.notification_email_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES),  # watch_matches query
        MagicMock(data=[{"id": "w1", "name": "AWS Watch"}]),  # watches query
        MagicMock(data=[]),  # update
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=True
    ) as mock_email:
        await dispatch_pending_notifications()

        mock_email.assert_called()


# ============================================================================
# ADMIN ALERT TESTS
# ============================================================================


# ---------------------------------------------------------------------------
# 14. Admin alert sends email
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_alert_sends_email(mock_smtp, test_settings):
    """Admin alert sends email to configured recipients."""
    from vigil.notifier import send_admin_alert

    test_settings.notification_email_recipients = "admin@example.com"

    await send_admin_alert("API Auth Failure", "Token expired")

    mock_smtp.send_message.assert_called_once()
    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert "[Vigil CRITICAL]" in sent_msg["Subject"]
    assert "API Auth Failure" in sent_msg["Subject"]


# ---------------------------------------------------------------------------
# 15. Admin alert email failure does not raise
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_alert_email_failure_does_not_raise(mock_smtp, test_settings):
    """Email failure in admin alert should be logged, not raised."""
    from vigil.notifier import send_admin_alert

    test_settings.notification_email_recipients = "admin@example.com"
    mock_smtp.send_message.side_effect = Exception("SMTP down")

    # Should not raise
    await send_admin_alert("API Auth Failure", "Token expired")


# ============================================================================
# RETRY COUNT INCREMENT TESTS
# ============================================================================


# ---------------------------------------------------------------------------
# 16. Dispatch increments retry_count on failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_increments_retry_count_on_failure(
    patch_supabase, mock_supabase, test_settings
):
    """When notification fails, retry_count should be incremented."""
    from vigil.notifier import dispatch_pending_notifications

    test_settings.notification_email_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES),  # watch_matches query
        MagicMock(data=[{"id": "w1", "name": "AWS Watch"}]),  # watches query
        MagicMock(data=[{}]),  # retry_count update
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=False
    ):
        await dispatch_pending_notifications()

    # Verify retry_count was incremented via update call
    update_calls = mock_supabase.table.return_value.update.call_args_list
    retry_updates = [c for c in update_calls if "retry_count" in str(c)]
    assert len(retry_updates) >= 1


# ============================================================================
# DAILY DIGEST TESTS
# ============================================================================


# ---------------------------------------------------------------------------
# 17. Daily digest content
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_daily_digest_content(patch_supabase, mock_supabase, test_settings):
    """5 matches across 2 watches -> summary email."""
    from vigil.notifier import send_daily_digest

    test_settings.daily_digest_enabled = True
    test_settings.notification_email_recipients = "a@b.com"

    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=SAMPLE_MATCHES_FIVE),  # watch_matches gte query
        MagicMock(
            data=[  # watches query
                {"id": "w1", "name": "AWS Watch"},
                {"id": "w2", "name": "IP Watch"},
            ]
        ),
    ]

    with patch(
        "vigil.notifier.send_email_alert", new_callable=AsyncMock, return_value=True
    ) as mock_email:
        await send_daily_digest()

        mock_email.assert_called()
        # Should include summary of all matches
        call_args = mock_email.call_args
        matches_arg = (
            call_args[0][1] if call_args[0] else call_args[1].get("matches", [])
        )
        assert len(matches_arg) >= 1


# ---------------------------------------------------------------------------
# 18. Daily digest disabled
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_daily_digest_disabled(patch_supabase, mock_supabase, test_settings):
    """daily_digest_enabled=false -> no send."""
    from vigil.notifier import send_daily_digest

    test_settings.daily_digest_enabled = False

    with patch("vigil.notifier.send_email_alert", new_callable=AsyncMock) as mock_email:
        await send_daily_digest()

        mock_email.assert_not_called()
    mock_supabase.table.assert_not_called()
