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
            resp_ = parties[idx + 4:]
        else:
            pet = parties

        body += (
            f'<tr data-diary-no="{diary_no}">'
            f'  <td data-th="Serial Number"><span class="bt-content">{serial}</span></td>'
            f'  <td data-th="Diary Number"><span class="bt-content">{diary_no}</span></td>'
            f'  <td data-th="Case Number"><span class="bt-content">{case_no}</span></td>'
            f'  <td class="petitioners" data-th="Petitioner / Respondent">'
            f'    <span class="bt-content"><div>{pet}</div><div>VS<br>{resp_}</div></span>'
            f'  </td>'
            f'  <td data-th="Petitioner/Respondent Advocate"><span class="bt-content">{advocate}</span></td>'
            f'  <td class="bt-hide"></td>'
            f'  <td class="bt-hide"></td>'
            f'  <td data-th="ROP"><span class="bt-content">'
            f'    <a target="_blank" href="{pdf_path}">{dt}</a><br>'
            f'  </span></td>'
            f'</tr>'
        )
    return f"<table>{header}<tbody>{body}</tbody></table>"


# ── Math Expression Parsing ──────────────────────────────


class TestParseMathExpression:
    """Tests for _parse_math_expression (extracted parser, no OCR involved)."""

    def test_addition(self):
        assert SCClient._parse_math_expression("3 + 5 = ?") == 8

    def test_subtraction(self):
        assert SCClient._parse_math_expression("12 - 4 = ?") == 8

    def test_multiplication_with_x(self):
        assert SCClient._parse_math_expression("6 x 3 = ?") == 18

    def test_multiplication_with_asterisk(self):
        assert SCClient._parse_math_expression("7 * 2 = ?") == 14

    def test_uppercase_X_multiplication(self):
        assert SCClient._parse_math_expression("3 X 5 = ?") == 15

    def test_division(self):
        assert SCClient._parse_math_expression("8 / 2 = ?") == 4

    def test_no_whitespace(self):
        assert SCClient._parse_math_expression("3+5=?") == 8

    def test_unicode_minus_en_dash(self):
        assert SCClient._parse_math_expression("8 \u2013 3 = ?") == 5

    def test_unicode_minus_em_dash(self):
        assert SCClient._parse_math_expression("8 \u2014 3 = ?") == 5

    def test_unicode_multiply(self):
        assert SCClient._parse_math_expression("4 \u00d7 3 = ?") == 12

    def test_unparseable_raises(self):
        with pytest.raises(SCCaptchaError, match="Could not parse"):
            SCClient._parse_math_expression("garbled text")

    def test_only_equals_sign(self):
        with pytest.raises(SCCaptchaError, match="Could not parse"):
            SCClient._parse_math_expression("= ?")


# ── Multi-Strategy Captcha Solving ───────────────────────


class TestSolveMathCaptcha:
    """Tests for _solve_math_captcha with parallel + confidence-based selection."""

    async def test_high_confidence_parallel_returns_immediately(self):
        """When a parallel-batch strategy returns >80 confidence, use it."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            return_value=("3 + 5 = ?", 95.0),
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 8

    async def test_low_confidence_picks_best_candidate(self):
        """When all strategies return low confidence, pick the highest."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        # Return parseable results with varying confidence — all below 80
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            side_effect=[
                ("3 + 5 = ?", 60.0),   # answer=8, conf=60
                ("6 x 3 = ?", 75.0),   # answer=18, conf=75 (best)
                ("1 + 1 = ?", 50.0),   # answer=2, conf=50
                ("4 + 2 = ?", 70.0),   # answer=6, conf=70
                ("2 + 3 = ?", 65.0),   # answer=5, conf=65
                ("9 - 1 = ?", 55.0),   # answer=8, conf=55
            ],
        ):
            result = await client._solve_math_captcha(image_bytes)
        # Should pick conf=75 → answer=18
        assert result == 18

    async def test_fallback_to_sequential_strategies(self):
        """When parallel batch fails, sequential strategies are tried."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        # Parallel batch (3): garbled, then sequential succeeds
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            side_effect=[
                ("garbled", 10.0),
                ("also garbled", 15.0),
                ("nope", 5.0),
                ("6 x 3 = ?", 90.0),  # Sequential strategy succeeds with high conf
            ],
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 18

    async def test_all_strategies_fail_raises(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with (
            patch.object(
                client, "_ocr_with_config", new_callable=AsyncMock,
                return_value=("garbled", 10.0),
            ),
            patch.object(client, "_log_captcha_failure") as mock_log,
        ):
            with pytest.raises(SCCaptchaError, match="strategies"):
                await client._solve_math_captcha(image_bytes)
            mock_log.assert_called_once()

    async def test_subtraction(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            return_value=("12 - 4 = ?", 90.0),
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 8

    async def test_multiplication_with_asterisk(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            return_value=("7 * 2 = ?", 85.0),
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 14

    async def test_ocr_exception_in_parallel_batch_skipped(self):
        """If some parallel strategies raise exceptions, others still work."""
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            side_effect=[
                SCCaptchaError("timeout"),    # parallel 1 fails
                ("5 + 3 = ?", 90.0),          # parallel 2 succeeds
                SCCaptchaError("timeout"),    # parallel 3 fails
            ],
        ):
            result = await client._solve_math_captcha(image_bytes)
        assert result == 8

    async def test_strategy_success_tracking(self):
        """Successful strategies should increment their success counters."""
        from vigil.sc_client import _strategy_success_counts
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()

        # Reset counters
        for k in _strategy_success_counts:
            _strategy_success_counts[k] = 0

        with patch.object(
            client, "_ocr_with_config", new_callable=AsyncMock,
            return_value=("3 + 5 = ?", 95.0),
        ):
            await client._solve_math_captcha(image_bytes)

        # At least one strategy should have been incremented
        assert sum(_strategy_success_counts.values()) >= 1


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
        html = _make_results_html([
            ("1", "132-2026", "SLP(C) 12345/2025", "X vs Y", "ADV",
             "https://api.sci.gov.in/pdf/order.pdf|21-02-2026"),
        ])
        assert client._is_captcha_rejection(html) is False

    def test_accepts_no_results_message_with_table(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        # A proper "no results" response with a table structure
        html = "<table><thead><tr><th>Case Number</th></tr></thead><tbody></tbody></table>"
        assert client._is_captcha_rejection(html) is False


# ── OCR With Config ──────────────────────────────────────


def _mock_tess_data(text: str, confidence: int = 90) -> dict:
    """Build a pytesseract.image_to_data DICT result for the given text."""
    words = text.split()
    return {
        "text": ["", *words, ""],  # Tesseract includes empties
        "conf": ["-1", *([str(confidence)] * len(words)), "-1"],
    }


class TestOcrWithConfig:
    """Tests for _ocr_with_config preprocessing pipeline (returns text + confidence)."""

    async def test_default_strategy(self):
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig("test", threshold=140, contrast_cutoff=5, upscale=3)

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("3 + 5 = ?", 92)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "3 + 5 = ?"
        assert conf == 92.0
        mock_tess.image_to_data.assert_called_once()

    async def test_inverted_strategy(self):
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_inv", threshold=140, contrast_cutoff=5, upscale=3, invert=True,
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("7 - 2 = ?", 85)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "7 - 2 = ?"
        assert conf == 85.0

    async def test_sharpen_strategy(self):
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_sharp", threshold=140, contrast_cutoff=5, upscale=4, sharpen=True,
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("4 x 2 = ?", 88)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "4 x 2 = ?"
        assert conf == 88.0

    async def test_psm6_strategy(self):
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_psm6", threshold=140, contrast_cutoff=5, upscale=3, psm=6,
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("9 + 1 = ?", 80)
            await client._ocr_with_config(image_bytes, config)

        call_args = mock_tess.image_to_data.call_args
        assert "--psm 6" in call_args[1]["config"]

    async def test_adaptive_threshold_strategy(self):
        """Adaptive threshold config is accepted without error."""
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_adaptive", threshold=0, contrast_cutoff=5, upscale=3,
            adaptive_threshold=True, morph_close=True, blur_type="gaussian",
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("5 + 3 = ?", 91)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "5 + 3 = ?"
        assert conf == 91.0

    async def test_morph_open_and_close(self):
        """Both morphological operations can be enabled together."""
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_morph", threshold=100, contrast_cutoff=8, upscale=4,
            morph_close=True, morph_open=True, sharpen=True,
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("2 + 7 = ?", 87)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "2 + 7 = ?"

    async def test_gaussian_blur_option(self):
        """Gaussian blur type is accepted without error."""
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_gauss", threshold=140, contrast_cutoff=5, upscale=3,
            blur_type="gaussian",
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("8 - 3 = ?", 93)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "8 - 3 = ?"

    async def test_no_blur_option(self):
        """blur_type='none' skips filtering."""
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig(
            "test_noblur", threshold=140, contrast_cutoff=5, upscale=3,
            blur_type="none",
        )

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            mock_tess.image_to_data.return_value = _mock_tess_data("1 + 2 = ?", 70)
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "1 + 2 = ?"
        assert conf == 70.0

    async def test_low_confidence_returned(self):
        """Confidence score is correctly computed from OCR data."""
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig("test", threshold=140, contrast_cutoff=5, upscale=3)

        with patch("vigil.sc_client.pytesseract") as mock_tess:
            mock_tess.Output.DICT = "dict"
            # Mix of confidences: 30, 80, 50 → avg 53.3
            mock_tess.image_to_data.return_value = {
                "text": ["", "3", "+", "5", ""],
                "conf": ["-1", "30", "80", "50", "-1"],
            }
            text, conf = await client._ocr_with_config(image_bytes, config)

        assert text == "3 + 5"
        assert abs(conf - 53.3) < 0.5

    async def test_ocr_timeout_raises_captcha_error(self):
        """When Tesseract hangs and times out, should raise SCCaptchaError."""
        import asyncio
        from vigil.sc_client import _PreprocessConfig
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()
        config = _PreprocessConfig("test", threshold=140, contrast_cutoff=5, upscale=3)

        # Patch asyncio.wait_for to immediately timeout
        with patch("vigil.sc_client.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with pytest.raises(SCCaptchaError, match="timed out"):
                await client._ocr_with_config(image_bytes, config)


# ── HTML Table Parsing ───────────────────────────────────


class TestParseResultsTable:
    def test_valid_table(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "132-2026", "SLP(C) 12345/2025", "X vs Y", "ADV NAME",
             "https://api.sci.gov.in/pdf/order.pdf|21-02-2026"),
        ])
        records = client._parse_results_table(html)
        assert len(records) == 1
        assert records[0].case_number == "SLP(C) 12345/2025"
        assert records[0].diary_number == "132-2026"
        assert records[0].parties == "X VSY"
        assert records[0].order_date == date(2026, 2, 21)
        assert records[0].pdf_url == "https://api.sci.gov.in/pdf/order.pdf"

    def test_multiple_rows(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "100-2026", "SLP(C) 111/2025", "A vs B", "ADV1",
             "https://api.sci.gov.in/pdf/1.pdf|21-02-2026"),
            ("2", "200-2026", "WP(C) 222/2025", "C vs D", "ADV2",
             "https://api.sci.gov.in/pdf/2.pdf|20-02-2026"),
        ])
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
        html = _make_results_html([
            ("1", "132-2026", "SLP(C) 12345/2025", "X vs Y", "ADV",
             "https://cdn.sci.gov.in/pdf/order.pdf|21-02-2026"),
        ])
        records = client._parse_results_table(html)
        assert records[0].pdf_url == "https://cdn.sci.gov.in/pdf/order.pdf"

    def test_invalid_date(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        html = _make_results_html([
            ("1", "132-2026", "SLP(C) 12345/2025", "X vs Y", "ADV",
             "https://api.sci.gov.in/pdf/order.pdf|invalid-date"),
        ])
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
            ("1", "132-2026", "SLP(C) 12345/2025", "X vs Y", "ADV",
             "https://api.sci.gov.in/pdf/order.pdf|21-02-2026"),
        ])

        captcha_image = _make_captcha_image_bytes()

        mock_responses = [
            # GET page
            httpx.Response(200, text=captcha_page_html,
                          request=httpx.Request("GET", "https://test.sci.gov.in/daily-order-rop-date/")),
            # GET captcha image
            httpx.Response(200, content=captcha_image,
                          request=httpx.Request("GET", "https://test.sci.gov.in/?_siwp_captcha&id=abc123")),
            # GET form submission (was POST, now GET with query params)
            httpx.Response(200, text=results_html,
                          request=httpx.Request("GET", "https://test.sci.gov.in/wp-admin/admin-ajax.php")),
        ]

        with (
            patch.object(client, "_rate_limit", new_callable=AsyncMock),
            patch.object(client._client, "get", new_callable=AsyncMock,
                        side_effect=[mock_responses[0], mock_responses[1], mock_responses[2]]),
            patch.object(client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8),
        ):
            orders = await client.fetch_daily_orders(
                date(2026, 2, 19), date(2026, 2, 21)
            )

        assert len(orders) == 1
        assert orders[0].case_number == "SLP(C) 12345/2025"
        assert orders[0].diary_number == "132-2026"

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
            patch.object(client, "_solve_math_captcha", new_callable=AsyncMock,
                        side_effect=SCCaptchaError("Could not parse")),
        ):
            with pytest.raises(SCCaptchaError, match="Failed to solve captcha"):
                await client.fetch_daily_orders(date(2026, 2, 19), date(2026, 2, 21))

    async def test_captcha_rejection_triggers_retry(self, patch_supabase, test_settings):
        """When server returns HTTP 200 with captcha rejection text, should retry."""
        client = SCClient(
            base_url="https://test.sci.gov.in", timeout=5,
            rate_limit_seconds=0, captcha_max_attempts=2,
        )

        captcha_page_html = (
            '<html><body>'
            '<img src="https://test.sci.gov.in/?_siwp_captcha&id=abc123">'
            '</body></html>'
        )
        captcha_image = _make_captcha_image_bytes()
        results_html = _make_results_html([
            ("1", "100-2026", "SLP(C) 111/2025", "A vs B", "ADV",
             "https://api.sci.gov.in/pdf/1.pdf|21-02-2026"),
        ])

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
                            # Attempt 1: AJAX returns rejection
                            httpx.Response(200, text="Incorrect captcha value",
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 2: page
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 2: captcha image
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # Attempt 2: AJAX returns valid results
                            httpx.Response(200, text=results_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                        ]),
            patch.object(client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8),
        ):
            orders = await client.fetch_daily_orders(
                date(2026, 2, 19), date(2026, 2, 21)
            )

        assert len(orders) == 1
        assert orders[0].case_number == "SLP(C) 111/2025"

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
                            # GET page
                            httpx.Response(200, text=captcha_page_html,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # GET captcha image
                            httpx.Response(200, content=captcha_image,
                                          request=httpx.Request("GET", "https://test.sci.gov.in/")),
                            # GET form submission (was POST, now GET) — returns 500
                            httpx.Response(
                                500, text="Internal Server Error",
                                request=httpx.Request("GET", "https://test.sci.gov.in/"),
                            ),
                        ]),
            patch.object(client, "_solve_math_captcha", new_callable=AsyncMock, return_value=8),
        ):
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


# ── Diagnostic Logging ───────────────────────────────────


class TestDiagnosticLogging:
    def test_log_captcha_failure_logs_image_info(self):
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()

        with patch("vigil.sc_client.logger") as mock_logger:
            client._log_captcha_failure(image_bytes, "garbled")

        # Should have logged the diagnostic info
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args_list[0]
        assert "CAPTCHA_DIAGNOSTIC" in call_args[0][0]

    def test_log_captcha_failure_saves_to_disk(self, tmp_path, test_settings):
        test_settings.sc_captcha_debug_dir = str(tmp_path)
        client = SCClient(base_url="https://test.sci.gov.in", timeout=5)
        image_bytes = _make_captcha_image_bytes()

        client._log_captcha_failure(image_bytes, "garbled")

        # Should have saved a PNG file
        saved_files = list(tmp_path.glob("captcha_fail_*.png"))
        assert len(saved_files) == 1
        assert saved_files[0].read_bytes() == image_bytes
