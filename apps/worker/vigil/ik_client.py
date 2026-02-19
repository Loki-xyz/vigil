"""
Indian Kanoon API Client.

DESIGN PRINCIPLES:
1. Every API call is logged to api_call_log via Supabase.
2. All calls have timeouts (30s default).
3. Retries with exponential backoff on 5xx and network errors.
4. Never retry on 4xx — these are bugs, not transient errors.
5. Rate limiting: max 1 request per 2 seconds (asyncio.Semaphore + sleep).
6. All methods are async.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)


class IKAPIError(Exception):
    """Base exception for IK API errors."""
    ...


class IKAPIAuthError(IKAPIError):
    """403 — pause all polling."""
    ...


class IKAPITimeoutError(IKAPIError):
    """Timeout after retries."""
    ...


class IKAPIRateLimitError(IKAPIError):
    """429 — back off."""
    ...


class IKClient:
    """Async client for the Indian Kanoon API."""

    def __init__(self, base_url: str, token: str, timeout: int = 30, max_retries: int = 3):
        self._semaphore = asyncio.Semaphore(1)
        self._last_request_time: float = 0.0
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Token {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def _rate_limit(self) -> None:
        """Ensure minimum 2 seconds between requests."""
        async with self._semaphore:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < 2.0:
                await asyncio.sleep(2.0 - elapsed)
            self._last_request_time = time.monotonic()

    async def _log_call(
        self,
        endpoint: str,
        url: str,
        watch_id: str | None,
        http_status: int | None,
        result_count: int | None,
        response_time_ms: int | float,
        error_message: str | None,
    ) -> None:
        """Insert into api_call_log table. Fire-and-forget — never raises."""
        try:
            supabase.table("api_call_log").insert({
                "endpoint": endpoint,
                "request_url": url,
                "watch_id": watch_id,
                "http_status": http_status,
                "result_count": result_count,
                "response_time_ms": int(response_time_ms),
                "error_message": error_message,
            }).execute()
        except Exception:
            logger.warning("Failed to log API call", exc_info=True)

    async def _request(
        self,
        endpoint: str,
        url: str,
        params: dict | None = None,
        watch_id: str | None = None,
        method: str = "POST",
    ) -> dict:
        """Make an HTTP request with retry logic, rate limiting, and logging."""
        await self._rate_limit()
        last_exc: Exception | None = None

        for attempt in range(1 + self._max_retries):
            start = time.monotonic()
            try:
                if method == "POST":
                    resp = await self._client.post(url, data=params)
                else:
                    resp = await self._client.get(url, params=params)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                # 403 — auth error, never retry
                if resp.status_code == 403:
                    await self._log_call(endpoint, str(resp.url), watch_id, 403, None, elapsed_ms, "Auth error")
                    raise IKAPIAuthError("IK API returned 403 — check API token")

                # 429 — rate limited, never retry
                if resp.status_code == 429:
                    await self._log_call(endpoint, str(resp.url), watch_id, 429, None, elapsed_ms, "Rate limited")
                    raise IKAPIRateLimitError("IK API returned 429 — rate limited")

                # 4xx (not 403/429) — client error, never retry
                if 400 <= resp.status_code < 500:
                    await self._log_call(endpoint, str(resp.url), watch_id, resp.status_code, None, elapsed_ms, f"Client error {resp.status_code}")
                    raise IKAPIError(f"Client error {resp.status_code}")

                # 5xx — server error, retry with backoff
                if resp.status_code >= 500:
                    last_exc = IKAPIError(f"Server error {resp.status_code}")
                    await self._log_call(endpoint, str(resp.url), watch_id, resp.status_code, None, elapsed_ms, str(last_exc))
                    if attempt < self._max_retries:
                        await asyncio.sleep(2 ** (attempt + 1))
                    continue

                # Success (2xx)
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    body_preview = resp.text[:500] if resp.text else "(empty)"
                    await self._log_call(
                        endpoint, str(resp.url), watch_id,
                        resp.status_code, None, elapsed_ms,
                        f"JSON parse error: {exc}",
                    )
                    logger.error(
                        "Malformed JSON from IK API (status %s): %s",
                        resp.status_code, body_preview,
                    )
                    raise IKAPIError(f"Malformed JSON response: {exc}") from exc
                count = len(data.get("docs", [])) if endpoint == "search" else None
                await self._log_call(endpoint, str(resp.url), watch_id, resp.status_code, count, elapsed_ms, None)
                return data

            except IKAPIError:
                raise
            except httpx.TimeoutException:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                last_exc = IKAPITimeoutError("Request timed out")
                await self._log_call(endpoint, url, watch_id, None, None, elapsed_ms, "Timeout")
                if attempt < self._max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))

        # All retries exhausted
        if isinstance(last_exc, IKAPITimeoutError):
            raise last_exc
        raise IKAPIError(f"Max retries ({self._max_retries}) exhausted")

    async def search(
        self, form_input: str, page_num: int = 0, watch_id: str | None = None
    ) -> dict:
        """
        POST /search/ with formInput=<query>&pagenum=<page>

        Returns parsed JSON response with docs array.
        Retries on 5xx/timeout with exponential backoff (2s, 4s, 8s).
        Raises IKAPIAuthError on 403, IKAPIRateLimitError on 429.
        """
        return await self._request(
            "search",
            "/search/",
            params={"formInput": form_input, "pagenum": page_num},
            watch_id=watch_id,
        )

    async def get_doc_meta(self, doc_id: int) -> dict:
        """
        POST /docmeta/<doc_id>/

        Returns parsed JSON with bench composition, acts cited, AI tags.
        """
        return await self._request("docmeta", f"/docmeta/{doc_id}/")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
