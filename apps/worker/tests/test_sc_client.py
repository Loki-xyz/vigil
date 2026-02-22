"""
Tests for vigil.sc_client — SC website scraper client.

All HTTP calls are mocked.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from vigil.sc_client import (
    SCCaptchaError,
    SCClient,
    SCOrderRecord,
    SCPDFDownloadError,
    SCWebsiteUnavailableError,
)


# ── Helpers ──────────────────────────────────────────────


def _make_captcha_image_bytes() -> bytes:
    """Create a minimal PNG image for testing (content doesn't matter — OCR is mocked)."""
    from PIL import Image

    img = Image.new("L", (150, 50), color=255)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_results_html(rows: list[tuple[str, str, str, str, str, str]]) -> str:
    """Build an HTML table matching the real SC website 8-column format.

    Each row tuple: (serial, diary_no, case_no, parties, advocate, pdf_path_and_date)
    where pdf_path_and_date is "url|dd-mm-yyyy" (pipe-separated).
    """
    header = (
        "<thead><tr>"
        "<th>Serial Number</th><th>Diary Number</th><th>Case Number</th>"
        "<th>Petitioner / Respondent</th><th>Petitioner/Respondent Advocate</th>"
        "<th>Bench</th><th>Judgment By</th><th>ROP</th>"
        "</tr></thead>"
    )
    body = ""
    for serial, diary_no, case_no, parties, advocate, pdf_date in rows:
        pdf_path, dt = pdf_date.split("|") if "|" in pdf_date else (pdf_date, "")
        pet, resp_ = ("", "")
        if " vs " in parties.lower():
            idx = parties.lower().index(" vs ")
            pet = parties[:idx]
            resp_ = parties[idx + 4 :]
        else:
            pet = parties

        body += (
            f'<tr data-diary-no="{diary_no}">'
            f'  <td data-th="Serial Number"><span class="bt-content">{serial}</span></td>'
            f'  <td data-th="Diary Number"><span class="bt-content">{diary_no}</span></td>'
            f'  <td data-th="Case Number"><span class="bt-content">{case_no}</span></td>'
            f'  <td class="petitioners" data-th="Petitioner / Respondent">'
            f'    <span class="bt-content"><div>{pet}</div><div>VS<br>{resp_}</div></span>'
            f"  </td>"
            f'  <td data-th="Petitioner/Respondent Advocate"><span class="bt-content">{advocate}</span></td>'
            f'  <td class="bt-hide"></td>'
            f'  <td class="bt-hide"></td>'
            f'  <td data-th="ROP"><span class="bt-content">'
            f'    <a target="_blank" href="{pdf_path}">{dt}</a><br>'
            f"  </span></td>"
            f"</tr>"
        )
    return f"<table>{header}<tbody>{body}</tbody></table>"


# ── Captcha Solving (LLM Solver) ─────────────────────────


class TestSolveMathCaptcha:
    """Tests for _solve_math_captcha which delegates to LLM captcha solver."""

    @pytest.fixture(autouse=True)
    def _reset_captcha_solver(self):
        from vigil.captcha_solver import reset_solver

        reset_solver()
        yield
        reset_solver()

    async def test_delegates_to_llm_solver(self):
        """_solve_math_captcha delegates to the LLM captcha solver."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        mock_solver = AsyncMock(return_value=8)
        with patch(
            "vigil.captcha_solver.get_captcha_solver",
            return_value=MagicMock(solve=mock_solver),
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 8
        mock_solver.assert_called_once_with(image_bytes)

    async def test_solver_error_propagates(self):
        """SCCaptchaError from solver propagates to caller."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        mock_solver = AsyncMock(side_effect=SCCaptchaError("LLM failed"))
        with patch(
            "vigil.captcha_solver.get_captcha_solver",
            return_value=MagicMock(solve=mock_solver),
        ):
            with pytest.raises(SCCaptchaError, match="LLM failed"):
                await client._solve_math_captcha(image_bytes)


# ── Captcha Rejection Detection ──────────────────────────


class TestCaptchaRejection:
    """Tests for _is_captcha_rejection."""

    def test_detects_incorrect_captcha(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        assert client._is_captcha_rejection("Incorrect captcha value") is True

    def test_detects_captcha_error(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        assert client._is_captcha_rejection("Captcha error: please try again") is True

    def test_detects_captcha_verification_failed(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        assert client._is_captcha_rejection("Captcha verification failed") is True

    def test_detects_empty_response(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        assert client._is_captcha_rejection("") is True

    def test_detects_short_error_response(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        assert client._is_captcha_rejection("error") is True

    def test_accepts_valid_table_response(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html(
            [
                (
                    "1",
                    "132-2026",
                    "SLP(C) 12345/2025",
                    "X vs Y",
                    "ADV",
                    "https://api.sci.gov.in/pdf/order.pdf|21-02-2026",
                ),
            ]
        )
        assert client._is_captcha_rejection(html) is False

    def test_accepts_no_results_message_with_table(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        # A proper "no results" response with a table structure
        html = (
            "<table><thead><tr><th>Case Number</th></tr></thead><tbody></tbody></table>"
        )
        assert client._is_captcha_rejection(html) is False


# ── HTML Table Parsing ───────────────────────────────────


class TestParseResultsTable:
    def test_valid_table(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html(
            [
                (
                    "1",
                    "132-2026",
                    "SLP(C) 12345/2025",
                    "X vs Y",
                    "ADV NAME",
                    "https://api.sci.gov.in/pdf/order.pdf|21-02-2026",
                ),
            ]
        )
        records = client._parse_results_table(html)
        assert len(records) == 1
        assert records[0].case_number == "SLP(C) 12345/2025"
        assert records[0].diary_number == "132-2026"
        assert records[0].parties == "X VSY"
        assert records[0].order_date == date(2026, 2, 21)
        assert records[0].pdf_url == "https://api.sci.gov.in/pdf/order.pdf"

    def test_multiple_rows(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html(
            [
                (
                    "1",
                    "100-2026",
                    "SLP(C) 111/2025",
                    "A vs B",
                    "ADV1",
                    "https://api.sci.gov.in/pdf/1.pdf|21-02-2026",
                ),
                (
                    "2",
                    "200-2026",
                    "WP(C) 222/2025",
                    "C vs D",
                    "ADV2",
                    "https://api.sci.gov.in/pdf/2.pdf|20-02-2026",
                ),
            ]
        )
        records = client._parse_results_table(html)
        assert len(records) == 2
        assert records[0].case_number == "SLP(C) 111/2025"
        assert records[0].diary_number == "100-2026"
        assert records[1].case_number == "WP(C) 222/2025"
        assert records[1].diary_number == "200-2026"

    def test_no_table_returns_empty(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        records = client._parse_results_table("<div>No results found</div>")
        assert records == []

    def test_absolute_pdf_url(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html(
            [
                (
                    "1",
                    "132-2026",
                    "SLP(C) 12345/2025",
                    "X vs Y",
                    "ADV",
                    "https://cdn.sci.gov.in/pdf/order.pdf|21-02-2026",
                ),
            ]
        )
        records = client._parse_results_table(html)
        assert records[0].pdf_url == "https://cdn.sci.gov.in/pdf/order.pdf"

    def test_invalid_date(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html(
            [
                (
                    "1",
                    "132-2026",
                    "SLP(C) 12345/2025",
                    "X vs Y",
                    "ADV",
                    "https://api.sci.gov.in/pdf/order.pdf|invalid-date",
                ),
            ]
        )
        records = client._parse_results_table(html)
        assert len(records) == 1
        assert records[0].order_date is None

    def test_rows_with_too_few_cells_skipped(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = "<table><tbody><tr><td>only one</td><td>two</td><td>three</td></tr></tbody></table>"
        records = client._parse_results_table(html)
        assert records == []


# ── Date Parsing ─────────────────────────────────────────


class TestParseDate:
    def test_dd_mm_yyyy_dash(self):
        assert SCClient._parse_date("21-02-2026") == date(2026, 2, 21)

    def test_dd_mm_yyyy_slash(self):
        assert SCClient._parse_date("21/02/2026") == date(2026, 2, 21)

    def test_dd_mm_yyyy_dot(self):
        assert SCClient._parse_date("21.02.2026") == date(2026, 2, 21)

    def test_invalid_returns_none(self):
        assert SCClient._parse_date("not-a-date") is None


# ── Fetch Daily Orders (Full Flow) ───────────────────────


class TestFetchDailyOrders:
    async def test_successful_fetch(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
            captcha_max_attempts=1,
        )

        captcha_page_html = (
            "<html><body>"
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '<input type="hidden" name="action" value="get_rop_data">'
            "</body></html>"
        )
        results_html = _make_results_html(
            [
                (
                    "1",
                    "132-2026",
                    "SLP(C) 12345/2025",
                    "X vs Y",
                    "ADV",
                    "https://api.sci.gov.in/pdf/order.pdf|21-02-2026",
                ),
            ]
        )

        captcha_image = _make_captcha_image_bytes()

        get_responses = [
            # GET page
            httpx.Response(
                200,
                text=captcha_page_html,
                request=httpx.Request(
                    "GET", "https://test.sci.gov.in/daily-order-rop-date/"
                ),
            ),
            # GET captcha image
            httpx.Response(
                200,
                content=captcha_image,
                request=httpx.Request(
                    "GET", "https://test.sci.gov.in/?_siwp_captcha&id=abc123"
                ),
            ),
        ]
        post_response = httpx.Response(
            200,
            text=results_html,
            request=httpx.Request(
                "POST", "https://test.sci.gov.in/wp-admin/admin-ajax.php"
            ),
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client, "get", new_callable=AsyncMock, side_effect=get_responses
            ),
            patch.object(
                client._client,
                "post",
                new_callable=AsyncMock,
                return_value=post_response,
            ),
            patch.object(
                client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8
            ),
        ):
            orders = await client.fetch_daily_orders(
                date(2026, 2, 19), date(2026, 2, 21)
            )

        assert len(orders) == 1
        assert orders[0].case_number == "SLP(C) 12345/2025"
        assert orders[0].diary_number == "132-2026"

    async def test_captcha_retry_on_failure(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
            captcha_max_attempts=3,
        )

        captcha_page_html = (
            "<html><body>"
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            "</body></html>"
        )
        captcha_image = _make_captcha_image_bytes()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                side_effect=[
                    # Attempt 1: page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 1: captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 2: page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 2: captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 3: page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 3: captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                ],
            ),
            patch.object(
                client,
                "_solve_math_captcha",
                new_callable=AsyncMock,
                side_effect=SCCaptchaError("Could not parse"),
            ),
        ):
            with pytest.raises(SCCaptchaError, match="Failed to solve captcha"):
                await client.fetch_daily_orders(date(2026, 2, 19), date(2026, 2, 21))

    async def test_captcha_rejection_triggers_retry(
        self, patch_supabase, test_settings
    ):
        """When server returns HTTP 200 with captcha rejection text, should retry."""
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
            captcha_max_attempts=2,
        )

        captcha_page_html = (
            "<html><body>"
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            "</body></html>"
        )
        captcha_image = _make_captcha_image_bytes()
        results_html = _make_results_html(
            [
                (
                    "1",
                    "100-2026",
                    "SLP(C) 111/2025",
                    "A vs B",
                    "ADV",
                    "https://api.sci.gov.in/pdf/1.pdf|21-02-2026",
                ),
            ]
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                side_effect=[
                    # Attempt 1: page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 1: captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 2: page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 2: captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                ],
            ),
            patch.object(
                client._client,
                "post",
                new_callable=AsyncMock,
                side_effect=[
                    # Attempt 1: AJAX returns rejection
                    httpx.Response(
                        200,
                        text="Incorrect captcha value",
                        request=httpx.Request("POST", "https://test.sci.gov.in/"),
                    ),
                    # Attempt 2: AJAX returns valid results
                    httpx.Response(
                        200,
                        text=results_html,
                        request=httpx.Request("POST", "https://test.sci.gov.in/"),
                    ),
                ],
            ),
            patch.object(
                client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8
            ),
        ):
            orders = await client.fetch_daily_orders(
                date(2026, 2, 19), date(2026, 2, 21)
            )

        assert len(orders) == 1
        assert orders[0].case_number == "SLP(C) 111/2025"

    async def test_website_unavailable_on_5xx(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
            captcha_max_attempts=1,
        )

        captcha_page_html = (
            "<html><body>"
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            "</body></html>"
        )
        captcha_image = _make_captcha_image_bytes()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                side_effect=[
                    # GET page
                    httpx.Response(
                        200,
                        text=captcha_page_html,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                    # GET captcha image
                    httpx.Response(
                        200,
                        content=captcha_image,
                        request=httpx.Request("GET", "https://test.sci.gov.in/"),
                    ),
                ],
            ),
            patch.object(
                client._client,
                "post",
                new_callable=AsyncMock,
                return_value=httpx.Response(
                    500,
                    text="Internal Server Error",
                    request=httpx.Request("POST", "https://test.sci.gov.in/"),
                ),
            ),
            patch.object(
                client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8
            ),
        ):
            with pytest.raises(SCWebsiteUnavailableError):
                await client.fetch_daily_orders(date(2026, 2, 19), date(2026, 2, 21))


# ── PDF Download and Parse ───────────────────────────────


class TestDownloadAndParsePdf:
    async def test_successful_pdf_parse(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
        )

        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is the order text.\nPage 1."

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.close = MagicMock()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                return_value=httpx.Response(
                    200,
                    content=b"fake-pdf-bytes",
                    request=httpx.Request("GET", "https://test.sci.gov.in/"),
                ),
            ),
            patch("vigil.sc_client.fitz", create=True) as mock_fitz,
        ):
            mock_fitz.open.return_value = mock_doc
            text = await client.download_and_parse_pdf(
                "https://test.sci.gov.in/pdf/order.pdf"
            )

        assert "This is the order text" in text
        mock_doc.close.assert_called_once()

    async def test_pdf_download_http_error(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                return_value=httpx.Response(
                    404,
                    text="Not Found",
                    request=httpx.Request("GET", "https://test.sci.gov.in/"),
                ),
            ),
        ):
            with pytest.raises(SCPDFDownloadError, match="HTTP 404"):
                await client.download_and_parse_pdf(
                    "https://test.sci.gov.in/pdf/missing.pdf"
                )

    async def test_pdf_download_timeout(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                side_effect=httpx.TimeoutException("timeout"),
            ),
        ):
            with pytest.raises(SCPDFDownloadError, match="timed out"):
                await client.download_and_parse_pdf(
                    "https://test.sci.gov.in/pdf/order.pdf"
                )


# ── Captcha Session ──────────────────────────────────────


class TestGetCaptchaSession:
    async def test_no_captcha_image_raises(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                return_value=httpx.Response(
                    200,
                    text="<html><body>No captcha here</body></html>",
                    request=httpx.Request("GET", "https://test.sci.gov.in/"),
                ),
            ),
        ):
            with pytest.raises(
                SCWebsiteUnavailableError, match="Captcha image not found"
            ):
                await client._get_captcha_session()

    async def test_extracts_captcha_url_and_hidden_fields(
        self, patch_supabase, test_settings
    ):
        client = SCClient(
            base_url="https://test.sci.gov.in",
            timeout=5,
            rate_limit_seconds=0,
        )

        html = (
            "<html><body>"
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '<input type="hidden" name="action" value="get_rop_data">'
            '<input type="hidden" name="nonce" value="xyz789">'
            "</body></html>"
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                return_value=httpx.Response(
                    200,
                    text=html,
                    request=httpx.Request("GET", "https://test.sci.gov.in/"),
                ),
            ),
        ):
            captcha_url, hidden_fields, cookies = await client._get_captcha_session()

        assert "_siwp_captcha" in captcha_url
        assert hidden_fields["action"] == "get_rop_data"
        assert hidden_fields["nonce"] == "xyz789"
