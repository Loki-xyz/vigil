"""Tests for vigil/main.py — run() and main() entry point."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# 1. run() starts and stops scheduler
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_starts_and_stops_scheduler():
    """Patch setup_scheduler; asyncio.sleep raises KeyboardInterrupt
    -> scheduler.start() and scheduler.shutdown() called."""
    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()
    mock_scheduler.shutdown = MagicMock()

    with patch("vigil.main.setup_scheduler", return_value=mock_scheduler) as mock_setup, \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=KeyboardInterrupt):

        from vigil.main import run

        # run() should handle KeyboardInterrupt gracefully
        try:
            await run()
        except KeyboardInterrupt:
            pass  # acceptable if it propagates

    mock_setup.assert_called_once()
    mock_scheduler.start.assert_called_once()
    mock_scheduler.shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# 2. run() handles unexpected exceptions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_handles_unexpected_exception():
    """Unexpected exception -> logged, scheduler still shut down."""
    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()
    mock_scheduler.shutdown = MagicMock()

    with patch("vigil.main.setup_scheduler", return_value=mock_scheduler), \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("unexpected")):
        from vigil.main import run

        await run()

    mock_scheduler.shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# 3. main() calls asyncio.run
# ---------------------------------------------------------------------------
def test_main_calls_asyncio_run():
    """Patch asyncio.run -> called once."""
    with patch("asyncio.run") as mock_asyncio_run:
        from vigil.main import main

        main()

        mock_asyncio_run.assert_called_once()
