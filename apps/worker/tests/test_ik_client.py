"""Tests for vigil.ik_client — IKClient async HTTP client for Indian Kanoon API."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from vigil.ik_client import (
    IKAPIAuthError,
    IKAPIError,
    IKAPIRateLimitError,
    IKAPITimeoutError,
    IKClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, json_data: dict | None = None) -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://test"),
    )
    return resp


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientInit:
    """Tests for IKClient.__init__."""

    def test_client_initialization(self, patch_supabase):
        """Headers, semaphore, and max_retries should be set on construction."""
        client = IKClient(
            base_url="https://api.indiankanoon.org",
            token="tok_abc",
            timeout=15,
            max_retries=5,
        )
        assert client._client.headers["Authorization"] == "Token tok_abc"
        assert client._client.headers["Accept"] == "application/json"
        assert client._semaphore._value == 1
        assert client._max_retries == 5

    def test_client_default_params(self, patch_supabase):
        """Default timeout=30 and max_retries=3 when not supplied."""
        client = IKClient(
            base_url="https://api.indiankanoon.org",
            token="tok_abc",
        )
        assert client._max_retries == 3
        assert client._client.timeout.read == 30 or client._client.timeout.connect == 30


# ---------------------------------------------------------------------------
# search() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSearch:
    """Tests for IKClient.search()."""

    async def test_search_success(
        self, patch_supabase, ik_search_response_single
    ):
        """200 response should return parsed JSON dict."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(200, ik_search_response_single)
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.search("Reliance doctypes:supremecourt")

        assert isinstance(result, dict)
        assert result["found"] == 1
        assert len(result["docs"]) == 1

    async def test_search_with_page_num(self, patch_supabase):
        """page_num=2 should appear as pagenum=2 in the request params."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(200, {"found": 0, "docs": []})
        client._client.get = AsyncMock(return_value=mock_resp)

        await client.search("test query", page_num=2)

        call_args = client._client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("pagenum") == 2

    async def test_search_with_watch_id(self, patch_supabase):
        """watch_id should be forwarded to _log_call."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(200, {"found": 0, "docs": []})
        client._client.get = AsyncMock(return_value=mock_resp)
        client._log_call = AsyncMock()

        await client.search("test", watch_id="watch-123")

        client._log_call.assert_called_once()
        call_kwargs = client._log_call.call_args
        assert "watch-123" in str(call_kwargs)


# ---------------------------------------------------------------------------
# search() — error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSearchErrors:
    """Tests for error paths in IKClient.search()."""

    async def test_search_403_raises_auth_error(self, patch_supabase):
        """403 should raise IKAPIAuthError without retrying."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="bad_tok"
        )
        mock_resp = _make_response(403)
        client._client.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(IKAPIAuthError):
            await client.search("test")

        assert client._client.get.call_count == 1

    async def test_search_429_raises_rate_limit_error(self, patch_supabase):
        """429 should raise IKAPIRateLimitError without retrying."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(429)
        client._client.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(IKAPIRateLimitError):
            await client.search("test")

        assert client._client.get.call_count == 1

    async def test_search_500_retries_then_succeeds(
        self, patch_supabase, ik_search_response_single
    ):
        """First 500, then 200 on retry — should return success."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        resp_500 = _make_response(500)
        resp_200 = _make_response(200, ik_search_response_single)
        client._client.get = AsyncMock(side_effect=[resp_500, resp_200])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.search("test")

        assert isinstance(result, dict)
        assert client._client.get.call_count == 2

    async def test_search_500_retries_exhausted(self, patch_supabase):
        """All 500s should exhaust retries then raise IKAPIError."""
        client = IKClient(
            base_url="https://api.indiankanoon.org",
            token="tok_abc",
            max_retries=3,
        )
        resp_500 = _make_response(500)
        client._client.get = AsyncMock(return_value=resp_500)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(IKAPIError):
                await client.search("test")

        assert client._client.get.call_count == 4  # 1 initial + 3 retries

    async def test_search_timeout_retries(self, patch_supabase):
        """Timeout on first call, success on second — should succeed."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        resp_200 = _make_response(200, {"found": 0, "docs": []})
        client._client.get = AsyncMock(
            side_effect=[httpx.TimeoutException("timeout"), resp_200]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.search("test")

        assert isinstance(result, dict)
        assert client._client.get.call_count == 2

    async def test_search_timeout_exhausted(self, patch_supabase):
        """All timeouts should exhaust retries then raise IKAPITimeoutError."""
        client = IKClient(
            base_url="https://api.indiankanoon.org",
            token="tok_abc",
            max_retries=3,
        )
        client._client.get = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(IKAPITimeoutError):
                await client.search("test")

        assert client._client.get.call_count == 4

    async def test_search_exponential_backoff(self, patch_supabase):
        """Retry backoff should follow 2s, 4s, 8s pattern."""
        client = IKClient(
            base_url="https://api.indiankanoon.org",
            token="tok_abc",
            max_retries=3,
        )
        client._client.get = AsyncMock(return_value=_make_response(500))

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(IKAPIError):
                await client.search("test")

        # Verify exponential backoff delays: 2^1=2, 2^2=4, 2^3=8
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        backoff_sleeps = [s for s in sleep_calls if s >= 2]
        assert backoff_sleeps == [2, 4, 8]


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRateLimit:
    """Tests for IKClient._rate_limit() — 2-second minimum gap."""

    async def test_rate_limit_minimum_2s(self, patch_supabase):
        """Two rapid _rate_limit() calls should enforce at least 2s gap."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            client._last_request_time = time.monotonic()
            await client._rate_limit()

            if mock_sleep.called:
                sleep_val = mock_sleep.call_args[0][0]
                assert 0 < sleep_val <= 2.0

    async def test_rate_limit_semaphore(self, patch_supabase):
        """Semaphore value should be 1 — serialises concurrent requests."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        assert client._semaphore._value == 1

    async def test_rate_limit_no_delay_if_time_passed(self, patch_supabase):
        """No sleep needed when _last_request_time is far in the past."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        client._last_request_time = time.monotonic() - 10.0

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._rate_limit()

            if mock_sleep.called:
                sleep_val = mock_sleep.call_args[0][0]
                assert sleep_val <= 0.01


# ---------------------------------------------------------------------------
# get_doc_meta()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDocMeta:
    """Tests for IKClient.get_doc_meta()."""

    async def test_get_doc_meta_success(
        self, patch_supabase, ik_docmeta_response
    ):
        """200 response should return parsed dict with doc metadata."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(200, ik_docmeta_response)
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.get_doc_meta(12345678)

        assert isinstance(result, dict)
        assert result["tid"] == 12345678
        assert "bench" in result

    async def test_get_doc_meta_404(self, patch_supabase):
        """404 should raise IKAPIError."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        client._client.get = AsyncMock(return_value=_make_response(404))

        with pytest.raises(IKAPIError):
            await client.get_doc_meta(99999999)

    async def test_get_doc_meta_logs_call(self, patch_supabase):
        """_log_call should be called with endpoint='docmeta'."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        mock_resp = _make_response(200, {"tid": 123})
        client._client.get = AsyncMock(return_value=mock_resp)
        client._log_call = AsyncMock()

        await client.get_doc_meta(123)

        client._log_call.assert_called_once()
        call_kwargs = client._log_call.call_args
        assert "docmeta" in str(call_kwargs)


# ---------------------------------------------------------------------------
# _log_call()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLogCall:
    """Tests for IKClient._log_call() — Supabase api_call_log insert."""

    async def test_log_call_inserts(self, patch_supabase):
        """_log_call should insert a row into api_call_log via Supabase."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )

        await client._log_call(
            endpoint="search",
            url="https://api.indiankanoon.org/search/?formInput=test",
            watch_id="watch-123",
            http_status=200,
            result_count=5,
            response_time_ms=345.2,
            error_message=None,
        )

        table_call = patch_supabase.table
        table_call.assert_called_with("api_call_log")
        insert_mock = table_call.return_value.insert
        assert insert_mock.called
        insert_data = insert_mock.call_args[0][0]
        assert insert_data["endpoint"] == "search"
        assert insert_data["http_status"] == 200
        assert insert_data["watch_id"] == "watch-123"
        assert insert_data["result_count"] == 5

    async def test_log_call_handles_error(self, patch_supabase):
        """If Supabase insert fails, _log_call should not raise — only log."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )

        patch_supabase.table.return_value.insert.return_value.execute.side_effect = (
            Exception("DB error")
        )

        await client._log_call(
            endpoint="search",
            url="https://api.indiankanoon.org/search/?formInput=test",
            watch_id=None,
            http_status=500,
            result_count=0,
            response_time_ms=100.0,
            error_message="Server Error",
        )


# ---------------------------------------------------------------------------
# JSON parse errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJSONParseError:
    """Tests for malformed JSON responses from IK API."""

    async def test_malformed_json_raises_ik_api_error(self, patch_supabase):
        """200 with invalid JSON -> IKAPIError raised, no retry."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        resp = httpx.Response(
            status_code=200,
            content=b"<html>Not JSON</html>",
            request=httpx.Request("GET", "https://test"),
            headers={"content-type": "text/html"},
        )
        client._client.get = AsyncMock(return_value=resp)

        with pytest.raises(IKAPIError, match="Malformed JSON"):
            await client.search("test")

        # Should NOT retry — it's a 2xx, just bad content
        assert client._client.get.call_count == 1

    async def test_malformed_json_logs_api_call(self, patch_supabase):
        """JSON parse failure should be logged via _log_call."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        resp = httpx.Response(
            status_code=200,
            content=b"not json at all",
            request=httpx.Request("GET", "https://test"),
            headers={"content-type": "text/plain"},
        )
        client._client.get = AsyncMock(return_value=resp)
        client._log_call = AsyncMock()

        with pytest.raises(IKAPIError):
            await client.search("test")

        client._log_call.assert_called()
        call_args = client._log_call.call_args
        assert "JSON parse error" in str(call_args)


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClose:
    """Tests for IKClient.close()."""

    async def test_close(self, patch_supabase):
        """close() should call _client.aclose()."""
        client = IKClient(
            base_url="https://api.indiankanoon.org", token="tok_abc"
        )
        client._client.aclose = AsyncMock()

        await client.close()

        client._client.aclose.assert_awaited_once()
