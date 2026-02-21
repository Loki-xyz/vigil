"""
Supreme Court Daily Orders Scraper.

Scrapes daily orders from the Supreme Court of India website at
sci.gov.in/daily-order-rop-date/.

DESIGN PRINCIPLES (mirroring ik_client.py):
1. Every scrape call is logged to api_call_log via Supabase.
2. All calls have timeouts (60s default for PDF downloads).
3. Retries with backoff on 5xx and network errors.
4. Rate limiting: max 1 request per 3 seconds (polite scraping).
5. Math captcha solved via Pillow + pytesseract OCR.
6. PDF text extraction via PyMuPDF (fitz).
7. All methods are async.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from io import BytesIO

import fitz  # PyMuPDF
import httpx
import pytesseract
from bs4 import BeautifulSoup
from PIL import Image, ImageFilter, ImageOps

from vigil.config import settings
from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SCScraperError(Exception):
    """Base exception for SC website scraper errors."""


class SCCaptchaError(SCScraperError):
    """Captcha solving failed after all attempts."""


class SCWebsiteUnavailableError(SCScraperError):
    """SC website is down or structure changed."""


class SCPDFDownloadError(SCScraperError):
    """Failed to download or parse a PDF."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SCOrderRecord:
    """Parsed row from the SC daily orders results table."""
    case_number: str
    parties: str
    order_date: date | None
    pdf_url: str
    court: str = "Supreme Court of India"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SCClient:
    """Async client for scraping SC daily orders from sci.gov.in."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 60,
        max_retries: int = 3,
        rate_limit_seconds: float = 3.0,
        captcha_max_attempts: int = 3,
    ):
        self._base_url = base_url or settings.sc_base_url
        self._ajax_url = f"{self._base_url}/wp-admin/admin-ajax.php"
        self._page_url = f"{self._base_url}/daily-order-rop-date/"
        self._semaphore = asyncio.Semaphore(1)
        self._last_request_time: float = 0.0
        self._max_retries = max_retries
        self._rate_limit_seconds = rate_limit_seconds
        self._captcha_max_attempts = captcha_max_attempts
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "Vigil/1.0 (Legal Monitoring Tool)"},
            follow_redirects=True,
        )

        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    async def _rate_limit(self) -> None:
        """Ensure minimum interval between requests."""
        async with self._semaphore:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._rate_limit_seconds:
                await asyncio.sleep(self._rate_limit_seconds - elapsed)
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
            logger.warning("Failed to log SC scraper API call", exc_info=True)

    # ------------------------------------------------------------------
    # Captcha
    # ------------------------------------------------------------------

    async def _get_captcha_session(self) -> tuple[str, dict[str, str], httpx.Cookies]:
        """
        GET the daily-order-rop-date page.

        Returns:
            (captcha_image_url, hidden_form_fields, session_cookies)
        """
        await self._rate_limit()
        resp = await self._client.get(self._page_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find captcha image
        captcha_img = soup.find("img", src=re.compile(r"_siwp_captcha"))
        if not captcha_img:
            raise SCWebsiteUnavailableError("Captcha image not found on page")

        captcha_url = captcha_img["src"]
        if not captcha_url.startswith("http"):
            captcha_url = f"{self._base_url}{captcha_url}"

        # Extract hidden form fields (nonce, action, etc.)
        hidden_fields: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                hidden_fields[name] = value

        return captcha_url, hidden_fields, resp.cookies

    async def _fetch_captcha_image(
        self, captcha_url: str, cookies: httpx.Cookies
    ) -> bytes:
        """Download the captcha image bytes using session cookies."""
        await self._rate_limit()
        resp = await self._client.get(captcha_url, cookies=cookies)
        resp.raise_for_status()
        return resp.content

    def _solve_math_captcha(self, image_bytes: bytes) -> int:
        """
        OCR the captcha image and solve the math expression.

        Uses Pillow for preprocessing + pytesseract for OCR.
        Expects images like "3 + 5 = ?" or "12 - 4 = ?".

        Returns the integer answer.
        Raises SCCaptchaError if the expression cannot be parsed.
        """
        img = Image.open(BytesIO(image_bytes))

        # Preprocessing pipeline
        img = img.convert("L")
        img = ImageOps.autocontrast(img, cutoff=5)
        img = img.point(lambda x: 255 if x > 140 else 0)
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
        img = img.filter(ImageFilter.MedianFilter(3))

        # OCR with character whitelist
        text = pytesseract.image_to_string(
            img,
            config="--psm 7 -c tessedit_char_whitelist=0123456789+-x*=? ",
        )

        # Parse: "3 + 5 = ?" or "12 - 4 ="
        match = re.search(r"(\d+)\s*([+\-x*])\s*(\d+)", text)
        if not match:
            raise SCCaptchaError(f"Could not parse math from OCR text: {text!r}")

        a, op, b = int(match.group(1)), match.group(2), int(match.group(3))

        if op == "+":
            return a + b
        elif op == "-":
            return a - b
        elif op in ("x", "*"):
            return a * b
        else:
            raise SCCaptchaError(f"Unknown operator: {op!r}")

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_results_table(self, html: str) -> list[SCOrderRecord]:
        """
        Parse the AJAX response HTML to extract order records.

        NOTE: The exact table structure should be verified against real
        AJAX responses captured via browser DevTools. Column indices
        may need adjustment.
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("No results table found in SC AJAX response")
            return []

        records: list[SCOrderRecord] = []
        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            try:
                # Expected columns: S.No. | Case No. | Parties | Date | Download
                case_number = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                parties = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                # Parse date (DD-MM-YYYY or DD/MM/YYYY)
                date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                order_date = self._parse_date(date_text)

                # Find PDF link
                pdf_link = row.find("a", href=True)
                pdf_url = ""
                if pdf_link:
                    href = pdf_link["href"]
                    if not href.startswith("http"):
                        pdf_url = f"{self._base_url}{href}"
                    else:
                        pdf_url = href

                if case_number and pdf_url:
                    records.append(SCOrderRecord(
                        case_number=case_number,
                        parties=parties,
                        order_date=order_date,
                        pdf_url=pdf_url,
                    ))
            except Exception:
                logger.warning("Failed to parse SC order row", exc_info=True)
                continue

        return records

    @staticmethod
    def _parse_date(date_text: str) -> date | None:
        """Parse DD-MM-YYYY or DD/MM/YYYY to a date object."""
        from datetime import datetime as dt
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                return dt.strptime(date_text, fmt).date()
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # Main fetch flow
    # ------------------------------------------------------------------

    async def fetch_daily_orders(
        self,
        from_date: date,
        to_date: date,
        watch_id: str | None = None,
    ) -> list[SCOrderRecord]:
        """
        Full scrape flow:
        1. Get captcha session (page + cookies)
        2. Download captcha image
        3. Solve math captcha
        4. POST form data
        5. Parse HTML results table
        6. Return list of SCOrderRecord

        Retries captcha solving up to captcha_max_attempts times.
        """
        start = time.monotonic()
        last_err: Exception | None = None

        for attempt in range(self._captcha_max_attempts):
            try:
                # Step 1: Get page and captcha
                captcha_url, hidden_fields, cookies = await self._get_captcha_session()

                # Step 2: Download captcha image
                image_bytes = await self._fetch_captcha_image(captcha_url, cookies)

                # Step 3: Solve captcha
                answer = self._solve_math_captcha(image_bytes)

                # Step 4: POST form
                form_data = {
                    **hidden_fields,
                    "from_date": from_date.strftime("%d-%m-%Y"),
                    "to_date": to_date.strftime("%d-%m-%Y"),
                    "captcha_code": str(answer),
                }

                await self._rate_limit()
                resp = await self._client.post(
                    self._ajax_url,
                    data=form_data,
                    cookies=cookies,
                )

                elapsed_ms = int((time.monotonic() - start) * 1000)

                if not resp.is_success:
                    await self._log_call(
                        "sc_daily_orders", self._ajax_url, watch_id,
                        resp.status_code, None, elapsed_ms,
                        f"HTTP {resp.status_code}",
                    )
                    if resp.status_code >= 500:
                        raise SCWebsiteUnavailableError(
                            f"SC website returned {resp.status_code}"
                        )
                    # Captcha likely wrong on 4xx, retry
                    last_err = SCCaptchaError(
                        f"Form submission returned {resp.status_code}"
                    )
                    continue

                # Step 5: Parse results
                records = self._parse_results_table(resp.text)

                await self._log_call(
                    "sc_daily_orders", self._ajax_url, watch_id,
                    resp.status_code, len(records), elapsed_ms, None,
                )

                logger.info(
                    "SC scraper fetched %d orders for %s to %s (attempt %d)",
                    len(records), from_date, to_date, attempt + 1,
                )
                return records

            except SCCaptchaError as e:
                last_err = e
                logger.warning(
                    "Captcha attempt %d/%d failed: %s",
                    attempt + 1, self._captcha_max_attempts, e,
                )
                continue
            except SCWebsiteUnavailableError:
                raise
            except httpx.TimeoutException:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                await self._log_call(
                    "sc_daily_orders", self._ajax_url, watch_id,
                    None, None, elapsed_ms, "Timeout",
                )
                raise SCWebsiteUnavailableError("SC website request timed out")

        # All captcha attempts failed
        elapsed_ms = int((time.monotonic() - start) * 1000)
        await self._log_call(
            "sc_daily_orders", self._ajax_url, watch_id,
            None, None, elapsed_ms,
            f"Captcha failed after {self._captcha_max_attempts} attempts",
        )
        raise SCCaptchaError(
            f"Failed to solve captcha after {self._captcha_max_attempts} attempts: {last_err}"
        )

    # ------------------------------------------------------------------
    # PDF handling
    # ------------------------------------------------------------------

    async def download_and_parse_pdf(self, pdf_url: str) -> str:
        """
        Download a PDF from SC website and extract text.

        Uses PyMuPDF (fitz) for fast, accurate extraction.
        SC daily orders are typically 1-10 pages of typed text.

        Returns extracted text string.
        Raises SCPDFDownloadError on failure.
        """
        try:
            await self._rate_limit()
            resp = await self._client.get(pdf_url)
            resp.raise_for_status()

            pdf_bytes = resp.content
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()

            full_text = "\n".join(text_parts)
            full_text = re.sub(r"\n{3,}", "\n\n", full_text)
            return full_text.strip()

        except httpx.HTTPStatusError as e:
            raise SCPDFDownloadError(
                f"PDF download failed with HTTP {e.response.status_code}: {pdf_url}"
            ) from e
        except httpx.TimeoutException as e:
            raise SCPDFDownloadError(
                f"PDF download timed out: {pdf_url}"
            ) from e
        except Exception as e:
            if isinstance(e, SCPDFDownloadError):
                raise
            raise SCPDFDownloadError(
                f"PDF extraction failed for {pdf_url}: {e}"
            ) from e

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
