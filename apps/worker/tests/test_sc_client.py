"""
Tests for vigil.sc_client — SC website scraper client.

All HTTP calls are mocked. Pytesseract is mocked (never calls real OCR).
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


def _make_results_html(rows: list[tuple[str, str, str, str, str]]) -> str:
    """Build an HTML table matching the expected SC website format."""
    header = "<tr><th>S.No.</th><th>Case No.</th><th>Parties</th><th>Date</th><th>Download</th></tr>"
    body = ""
    for sno, case, parties, dt, pdf_path in rows:
        body += (
            f"<tr><td>{sno}</td><td>{case}</td><td>{parties}</td>"
            f"<td>{dt}</td><td><a href=\"{pdf_path}\">PDF</a></td></tr>"
        )
    return f"<table>{header}{body}</table>"


# ── Math Captcha Solving ─────────────────────────────────


class TestSolveMathCaptcha:
    def test_addition(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "3 + 5 = ?"
            result = client._solve_math_captcha(image_bytes)
        assert result == 8

    def test_subtraction(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "12 - 4 = ?"
            result = client._solve_math_captcha(image_bytes)
        assert result == 8

    def test_multiplication_with_x(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "6 x 3 = ?"
            result = client._solve_math_captcha(image_bytes)
        assert result == 18

    def test_multiplication_with_asterisk(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "7 * 2 = ?"
            result = client._solve_math_captcha(image_bytes)
        assert result == 14

    def test_unparseable_raises(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "garbled text"
            with pytest.raises(SCCaptchaError, match="Could not parse"):
                client._solve_math_captcha(image_bytes)

    def test_no_whitespace(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "3+5=?"
            result = client._solve_math_captcha(image_bytes)
        assert result == 8


# ── HTML Table Parsing ───────────────────────────────────


class TestParseResultsTable:
    def test_valid_table(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "SLP(C) 12345/2025", "X vs Y", "21-02-2026", "/pdf/order.pdf"),
        ])
        records = client._parse_results_table(html)
        assert len(records) == 1
        assert records[0].case_number == "SLP(C) 12345/2025"
        assert records[0].parties == "X vs Y"
        assert records[0].order_date == date(2026, 2, 21)
        assert records[0].pdf_url == "https://test.sci.gov.in/pdf/order.pdf"

    def test_multiple_rows(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "SLP(C) 111/2025", "A vs B", "21-02-2026", "/pdf/1.pdf"),
            ("2", "WP(C) 222/2025", "C vs D", "20-02-2026", "/pdf/2.pdf"),
        ])
        records = client._parse_results_table(html)
        assert len(records) == 2
        assert records[0].case_number == "SLP(C) 111/2025"
        assert records[1].case_number == "WP(C) 222/2025"

    def test_no_table_returns_empty(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        records = client._parse_results_table("<div>No results found</div>")
        assert records == []

    def test_absolute_pdf_url(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "SLP(C) 12345/2025", "X vs Y", "21-02-2026",
             "https://cdn.sci.gov.in/pdf/order.pdf"),
        ])
        records = client._parse_results_table(html)
        assert records[0].pdf_url == "https://cdn.sci.gov.in/pdf/order.pdf"

    def test_invalid_date(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "SLP(C) 12345/2025", "X vs Y", "invalid-date", "/pdf/order.pdf"),
        ])
        records = client._parse_results_table(html)
        assert len(records) == 1
        assert records[0].order_date is None

    def test_rows_with_too_few_cells_skipped(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = "<table><tr><th>H</th></tr><tr><td>only one</td></tr></table>"
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
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0, captcha_max_attempts=1,
        )

        captcha_page_html = (
            '<html><body>'
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '<input type="hidden" name="action" value="get_rop_data">'
            '</body></html>'
        )
        results_html = _make_results_html([
            ("1", "SLP(C) 12345/2025", "X vs Y", "21-02-2026", "/pdf/order.pdf"),
        ])

        captcha_image = _make_captcha_image_bytes()

        mock_responses = [
            # GET page
            httpx.Response(200, text=captcha_page_html,
                          request=httpx.Request("GET", "https://test.sci.gov.in/daily-order-rop-date/")),
            # GET captcha image
            httpx.Response(200, content=captcha_image,
                          request=httpx.Request("GET", "https://test.sci.gov.in/?_siwp_captcha&id=abc123")),
            # POST form
            httpx.Response(200, text=results_html,
                          request=httpx.Request("POST", "https://test.sci.gov.in/wp-admin/admin-ajax.php")),
        ]

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        side_effect=[mock_responses[0], mock_responses[1]]),
            patch.object(client._client, "post", new_callable=AsyncMock,
                        return_value=mock_responses[2]),
            patch("vigil.sc_client.pytesseract") as mock_tess,
        ):
            mock_tess.image_to_string.return_value = "3 + 5 = ?"

            orders = await client.fetch_daily_orders(
                date(2026, 2, 19), date(2026, 2, 21)
            )

        assert len(orders) == 1
        assert orders[0].case_number == "SLP(C) 12345/2025"

    async def test_captcha_retry_on_failure(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0, captcha_max_attempts=3,
        )

        captcha_page_html = (
            '<html><body>'
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '</body></html>'
        )
        captcha_image = _make_captcha_image_bytes()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        side_effect=[
                            # Attempt 1: page
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 1: captcha image
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 2: page
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 2: captcha image
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 3: page
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 3: captcha image
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                        ]),
            patch("vigil.sc_client.pytesseract") as mock_tess,
        ):
            # OCR always returns unparseable text
            mock_tess.image_to_string.return_value = "garbled"

            with pytest.raises(SCCaptchaError, match="Failed to solve captcha"):
                await client.fetch_daily_orders(date(2026, 2, 19), date(2026, 2, 21))

    async def test_website_unavailable_on_5xx(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0, captcha_max_attempts=1,
        )

        captcha_page_html = (
            '<html><body>'
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '</body></html>'
        )
        captcha_image = _make_captcha_image_bytes()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        side_effect=[
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                        ]),
            patch.object(client._client, "post", new_callable=AsyncMock,
                        return_value=httpx.Response(
                            500, text="Internal Server Error",
                            request=httpx.Request("POST", "https://test.sci.gov.in/"),
                        )),
            patch("vigil.sc_client.pytesseract") as mock_tess,
        ):
            mock_tess.image_to_string.return_value = "3 + 5 = ?"

            with pytest.raises(SCWebsiteUnavailableError):
                await client.fetch_daily_orders(date(2026, 2, 19), date(2026, 2, 21))


# ── PDF Download and Parse ───────────────────────────────


class TestDownloadAndParsePdf:
    async def test_successful_pdf_parse(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0,
        )

        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is the order text.\nPage 1."

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.close = MagicMock()

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        return_value=httpx.Response(
                            200, content=b"fake-pdf-bytes",
                            request=httpx.Request("GET", "https://test.sci.gov.in/"),
                        )),
            patch("vigil.sc_client.fitz", create=True) as mock_fitz,
        ):
            mock_fitz.open.return_value = mock_doc
            text = await client.download_and_parse_pdf("https://test.sci.gov.in/pdf/order.pdf")

        assert "This is the order text" in text
        mock_doc.close.assert_called_once()

    async def test_pdf_download_http_error(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        return_value=httpx.Response(
                            404, text="Not Found",
                            request=httpx.Request("GET", "https://test.sci.gov.in/"),
                        )),
        ):
            with pytest.raises(SCPDFDownloadError, match="HTTP 404"):
                await client.download_and_parse_pdf("https://test.sci.gov.in/pdf/missing.pdf")

    async def test_pdf_download_timeout(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        side_effect=httpx.TimeoutException("timeout")),
        ):
            with pytest.raises(SCPDFDownloadError, match="timed out"):
                await client.download_and_parse_pdf("https://test.sci.gov.in/pdf/order.pdf")


# ── Captcha Session ──────────────────────────────────────


class TestGetCaptchaSession:
    async def test_no_captcha_image_raises(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0,
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        return_value=httpx.Response(
                            200, text="<html><body>No captcha here</body></html>",
                            request=httpx.Request("GET", "https://test.sci.gov.in/"),
                        )),
        ):
            with pytest.raises(SCWebsiteUnavailableError, match="Captcha image not found"):
                await client._get_captcha_session()

    async def test_extracts_captcha_url_and_hidden_fields(self, patch_supabase, test_settings):
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0,
        )

        html = (
            '<html><body>'
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '<input type="hidden" name="action" value="get_rop_data">'
            '<input type="hidden" name="nonce" value="xyz789">'
            '</body></html>'
        )

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        return_value=httpx.Response(
                            200, text=html,
                            request=httpx.Request("GET", "https://test.sci.gov.in/"),
                        )),
        ):
            captcha_url, hidden_fields, cookies = await client._get_captcha_session()

        assert "_siwp_captcha" in captcha_url
        assert hidden_fields["action"] == "get_rop_data"
        assert hidden_fields["nonce"] == "xyz789"
