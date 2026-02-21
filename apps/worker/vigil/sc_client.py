"""
Supreme Court Daily Orders Scraper.

Scrapes daily orders from the Supreme Court of India website at
sci.gov.in/daily-order-rop-date/.

DESIGN PRINCIPLES (mirroring ik_client.py):
1. Every scrape call is logged to api_call_log via Supabase.
2. All calls have timeouts (60s default for PDF downloads).
3. Retries with backoff on 5xx and network errors.
4. Rate limiting: max 1 request per 3 seconds (polite scraping).
5. Math captcha solved via EasyOCR (primary) + pytesseract (fallback).
6. PDF text extraction via PyMuPDF (fitz).
7. All methods are async.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO

import cv2
import easyocr
import fitz  # PyMuPDF
import httpx
import numpy as np
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
    diary_number: str
    parties: str
    order_date: date | None
    pdf_url: str
    court: str = "Supreme Court of India"


@dataclass
class _PreprocessConfig:
    """One preprocessing strategy for captcha OCR."""
    name: str
    threshold: int
    contrast_cutoff: float
    upscale: int
    invert: bool = False
    sharpen: bool = False
    psm: int = 7
    adaptive_threshold: bool = False
    blur_type: str = "median"       # "median" | "gaussian" | "none"
    morph_close: bool = True        # fill small gaps in digit strokes
    morph_open: bool = False        # remove salt-and-pepper noise dots


# Strategies ordered by expected reliability. Top 3 run in parallel.
_PREPROCESS_STRATEGIES = [
    # --- Parallel batch (Group A) ---
    _PreprocessConfig(
        "adaptive_morph", threshold=0, contrast_cutoff=5, upscale=3,
        adaptive_threshold=True, morph_close=True, blur_type="gaussian",
    ),
    _PreprocessConfig(
        "default_morph", threshold=140, contrast_cutoff=5, upscale=3,
        morph_close=True, blur_type="gaussian",
    ),
    _PreprocessConfig(
        "high_thresh_morph", threshold=180, contrast_cutoff=3, upscale=3,
        morph_close=True,
    ),
    # --- Sequential fallbacks (Group B) ---
    _PreprocessConfig(
        "inverted_adaptive", threshold=0, contrast_cutoff=5, upscale=3,
        invert=True, adaptive_threshold=True, morph_close=True,
    ),
    _PreprocessConfig(
        "low_thresh_sharp", threshold=100, contrast_cutoff=8, upscale=4,
        sharpen=True, morph_close=True, morph_open=True,
    ),
    _PreprocessConfig(
        "high_contrast_clean", threshold=160, contrast_cutoff=0, upscale=3,
        morph_close=True, morph_open=True, blur_type="gaussian",
    ),
]

_PARALLEL_BATCH_SIZE = 3

# Module-level strategy success tracking (resets on process restart).
_strategy_success_counts: dict[str, int] = {s.name: 0 for s in _PREPROCESS_STRATEGIES}


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

    # ------------------------------------------------------------------
    # EasyOCR reader (singleton — heavy to initialize)
    # ------------------------------------------------------------------

    _easyocr_reader: easyocr.Reader | None = None

    @classmethod
    def _get_easyocr_reader(cls) -> easyocr.Reader:
        if cls._easyocr_reader is None:
            cls._easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return cls._easyocr_reader

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

        Hidden fields extracted (verified via browser DevTools):
            - scid: captcha session ID
            - tok_*: dynamic CSRF-like token
            - _ch_field: honeypot (must be empty)
            - es_ajax_request: always "1"
        """
        await self._rate_limit()
        resp = await self._client.get(self._page_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Scope to the ROP Date form specifically
        form = soup.find("form", id="sciapi-services-daily-order-rop-date")
        search_root = form or soup

        # Find captcha image
        captcha_img = search_root.find("img", src=re.compile(r"_siwp_captcha"))
        if not captcha_img:
            raise SCWebsiteUnavailableError("Captcha image not found on page")

        captcha_url = captcha_img["src"]
        if not captcha_url.startswith("http"):
            captcha_url = f"{self._base_url}{captcha_url}"

        # Extract hidden form fields (scid, tok_*, _ch_field, es_ajax_request)
        hidden_fields: dict[str, str] = {}
        for inp in search_root.find_all("input", {"type": "hidden"}):
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

    @staticmethod
    def _prepare_easyocr_variants(image_bytes: bytes) -> list[tuple[str, np.ndarray]]:
        """Prepare image variants for EasyOCR (preprocessed, raw, inverted)."""
        pil_img = Image.open(BytesIO(image_bytes))
        variants: list[tuple[str, np.ndarray]] = []

        # Variant 1: Preprocessed (autocontrast + threshold + upscale)
        gray = pil_img.convert("L")
        pre = ImageOps.autocontrast(gray, cutoff=5)
        pre = pre.point(lambda x: 255 if x > 140 else 0)
        pre = pre.resize((pre.width * 3, pre.height * 3), Image.LANCZOS)
        variants.append(("preprocessed", np.array(pre)))

        # Variant 2: Raw image (sometimes catches what preprocessing loses)
        variants.append(("raw", np.array(pil_img)))

        # Variant 3: Inverted + contrast (helps with light-colored captcha text)
        inv = ImageOps.autocontrast(gray, cutoff=5)
        inv = ImageOps.invert(inv)
        inv = inv.point(lambda x: 255 if x > 100 else 0)
        inv = inv.resize((inv.width * 3, inv.height * 3), Image.LANCZOS)
        variants.append(("inverted", np.array(inv)))

        return variants

    def _get_ordered_strategies(self) -> list[_PreprocessConfig]:
        """Return strategies ordered by historical success rate."""
        return sorted(
            _PREPROCESS_STRATEGIES,
            key=lambda s: _strategy_success_counts.get(s.name, 0),
            reverse=True,
        )

    async def _solve_math_captcha(self, image_bytes: bytes) -> int:
        """
        OCR the captcha image and solve the math expression.

        Three-phase approach for accuracy + speed:
          Phase 0: EasyOCR (deep learning) with 3 image variants.
                   Best at recognizing small/light operators (+, -, x).
          Phase 1: Run top 3 Tesseract+OpenCV strategies in parallel.
                   If any yields >80 confidence, return immediately.
          Phase 2: Run remaining Tesseract strategies sequentially,
                   collecting all parseable candidates. Pick highest confidence.

        Returns the integer answer.
        Raises SCCaptchaError if no strategy can parse the expression.
        """
        last_text = ""

        # Phase 0: EasyOCR with multiple image variants (best success rate)
        try:
            reader = self._get_easyocr_reader()
            easyocr_variants = self._prepare_easyocr_variants(image_bytes)

            for variant_name, img_array in easyocr_variants:
                try:
                    results = reader.readtext(
                        img_array, allowlist="0123456789+-x*/= ",
                    )
                    if not results:
                        continue
                    text = results[0][1]
                    conf = results[0][2]
                    if conf < 0.3:
                        last_text = text
                        continue
                    answer = self._parse_math_expression(text)
                    logger.debug(
                        "Captcha solved with EasyOCR %r: text=%r conf=%.2f answer=%d",
                        variant_name, text, conf, answer,
                    )
                    _strategy_success_counts["easyocr"] = (
                        _strategy_success_counts.get("easyocr", 0) + 1
                    )
                    return answer
                except SCCaptchaError:
                    if "text" in dir():
                        last_text = text
                    continue
        except Exception:
            logger.warning("EasyOCR failed, falling back to Tesseract", exc_info=True)

        # Phase 1: Tesseract parallel batch
        strategies = self._get_ordered_strategies()
        parallel_batch = strategies[:_PARALLEL_BATCH_SIZE]
        sequential_batch = strategies[_PARALLEL_BATCH_SIZE:]

        candidates: list[tuple[float, int, str, str]] = []  # (conf, answer, name, text)

        # Phase 1: parallel batch
        tasks = [
            self._ocr_with_config(image_bytes, cfg)
            for cfg in parallel_batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for cfg, result in zip(parallel_batch, results):
            if isinstance(result, Exception):
                continue
            text, confidence = result
            last_text = text
            try:
                answer = self._parse_math_expression(text)
                logger.debug(
                    "Captcha candidate from %r: text=%r, conf=%.1f, answer=%d",
                    cfg.name, text, confidence, answer,
                )
                if confidence > 80:
                    _strategy_success_counts[cfg.name] = (
                        _strategy_success_counts.get(cfg.name, 0) + 1
                    )
                    return answer
                candidates.append((confidence, answer, cfg.name, text))
            except SCCaptchaError:
                continue

        # Phase 2: sequential fallbacks
        for cfg in sequential_batch:
            try:
                text, confidence = await self._ocr_with_config(image_bytes, cfg)
                last_text = text
                answer = self._parse_math_expression(text)
                logger.debug(
                    "Captcha candidate from %r: text=%r, conf=%.1f, answer=%d",
                    cfg.name, text, confidence, answer,
                )
                if confidence > 80:
                    _strategy_success_counts[cfg.name] = (
                        _strategy_success_counts.get(cfg.name, 0) + 1
                    )
                    return answer
                candidates.append((confidence, answer, cfg.name, text))
            except SCCaptchaError:
                continue

        # Pick best candidate by confidence
        if candidates:
            candidates.sort(reverse=True)
            best_conf, best_answer, best_name, best_text = candidates[0]
            logger.info(
                "Captcha solved (best of %d candidates): strategy=%r, "
                "text=%r, conf=%.1f, answer=%d",
                len(candidates), best_name, best_text, best_conf, best_answer,
            )
            _strategy_success_counts[best_name] = (
                _strategy_success_counts.get(best_name, 0) + 1
            )
            return best_answer

        # All strategies failed
        self._log_captcha_failure(image_bytes, last_text)
        raise SCCaptchaError(
            f"Could not parse math from captcha after EasyOCR + "
            f"{len(_PREPROCESS_STRATEGIES)} Tesseract strategies. "
            f"Last OCR text: {last_text!r}"
        )

    async def _ocr_with_config(
        self, image_bytes: bytes, config: _PreprocessConfig,
    ) -> tuple[str, float]:
        """Apply a specific preprocessing config and return (text, confidence).

        Revised pipeline (optimised ordering):
          1. Grayscale + autocontrast
          2. Optional invert
          3. Upscale (before threshold — preserves subpixel info for LANCZOS)
          4. Blur (smooth upscale artifacts before binarisation)
          5. Threshold (global or adaptive via OpenCV)
          6. Morphological operations (on binary image)
          7. Optional sharpen
          8. 10px white border (Tesseract best practice)
          9. OCR with confidence scoring

        Runs Tesseract in a background thread with configurable timeout.
        """
        ocr_timeout = settings.sc_captcha_ocr_timeout

        def _do_ocr() -> tuple[str, float]:
            img = Image.open(BytesIO(image_bytes))
            img = img.convert("L")

            # 1. Auto-contrast
            if config.contrast_cutoff > 0:
                img = ImageOps.autocontrast(img, cutoff=config.contrast_cutoff)

            # 2. Optional invert
            if config.invert:
                img = ImageOps.invert(img)

            # 3. Upscale FIRST (preserves subpixel info for LANCZOS)
            img = img.resize(
                (img.width * config.upscale, img.height * config.upscale),
                Image.LANCZOS,
            )

            # 4. Blur (before threshold to smooth upscale artifacts)
            if config.blur_type == "gaussian":
                img = img.filter(ImageFilter.GaussianBlur(radius=1))
            elif config.blur_type == "median":
                img = img.filter(ImageFilter.MedianFilter(3))

            # 5. Threshold (after upscale + blur)
            img_array = np.array(img, dtype=np.uint8)
            if config.adaptive_threshold:
                img_array = cv2.adaptiveThreshold(
                    img_array, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    blockSize=11,
                    C=2,
                )
            elif config.threshold > 0:
                _, img_array = cv2.threshold(
                    img_array, config.threshold, 255, cv2.THRESH_BINARY,
                )

            # 6. Morphological operations (on binary image)
            if config.morph_close:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
            if config.morph_open:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                img_array = cv2.morphologyEx(img_array, cv2.MORPH_OPEN, kernel)

            # 7. Optional sharpen
            img = Image.fromarray(img_array)
            if config.sharpen:
                img = img.filter(ImageFilter.SHARPEN)

            # 8. 10px white border (Tesseract best practice for tight crops)
            img = ImageOps.expand(img, border=10, fill=255)

            # 9. OCR with confidence scoring
            tess_config = (
                f"--psm {config.psm} "
                '-c tessedit_char_whitelist="0123456789 +-xX*=?"'
            )
            data = pytesseract.image_to_data(
                img, config=tess_config, output_type=pytesseract.Output.DICT,
            )
            confidences = [
                int(c) for c, t in zip(data["conf"], data["text"])
                if t.strip() and int(c) > 0
            ]
            avg_conf = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )
            text = " ".join(t for t in data["text"] if t.strip())
            return text.strip(), avg_conf

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_do_ocr),
                timeout=ocr_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Tesseract OCR timed out after %.1fs with strategy %r",
                ocr_timeout, config.name,
            )
            raise SCCaptchaError(f"OCR timed out with strategy {config.name!r}")

    @staticmethod
    def _parse_math_expression(text: str) -> int:
        """Parse a math expression from OCR text and compute the answer."""
        # Normalize common OCR artifacts
        cleaned = text.replace("X", "x").replace("\u00d7", "x").replace("\u00f7", "/")
        cleaned = cleaned.replace("\u2014", "-").replace("\u2013", "-")
        cleaned = cleaned.replace("?", "").replace("=", "").strip()

        match = re.search(r"(\d+)\s*([+\-x*/])\s*(\d+)", cleaned)
        if not match:
            raise SCCaptchaError(f"Could not parse math from OCR text: {text!r}")

        a, op, b = int(match.group(1)), match.group(2), int(match.group(3))

        if op == "+":
            return a + b
        elif op == "-":
            return a - b
        elif op in ("x", "*"):
            return a * b
        elif op == "/":
            return a // b if b != 0 else 0
        else:
            raise SCCaptchaError(f"Unknown operator: {op!r}")

    def _is_captcha_rejection(self, response_text: str) -> bool:
        """Detect if the AJAX response indicates a wrong captcha answer."""
        text_lower = response_text.lower().strip()
        rejection_patterns = [
            "incorrect captcha",
            "captcha error",
            "captcha verification failed",
            "invalid captcha",
            "wrong captcha",
            "security code",
        ]
        for pattern in rejection_patterns:
            if pattern in text_lower:
                return True
        # Empty or very short response with no table is suspicious
        if len(text_lower) < 50 and "<table" not in text_lower:
            return True
        return False

    def _log_captcha_failure(self, image_bytes: bytes, last_ocr_text: str) -> None:
        """Log diagnostic info when all captcha strategies fail."""
        try:
            img = Image.open(BytesIO(image_bytes))
            logger.error(
                "CAPTCHA_DIAGNOSTIC: All strategies failed. "
                "Last OCR text: %r. Image: %dx%d mode=%s size=%d bytes",
                last_ocr_text, img.width, img.height, img.mode, len(image_bytes),
            )
        except Exception:
            logger.error(
                "CAPTCHA_DIAGNOSTIC: All strategies failed. "
                "Last OCR text: %r. Image size: %d bytes (could not open)",
                last_ocr_text, len(image_bytes),
            )

        # Optionally save to disk for debugging
        if settings.sc_captcha_debug_dir:
            try:
                os.makedirs(settings.sc_captcha_debug_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(settings.sc_captcha_debug_dir, f"captcha_fail_{ts}.png")
                with open(path, "wb") as f:
                    f.write(image_bytes)
                logger.error("CAPTCHA_DIAGNOSTIC: Saved failed captcha to %s", path)
            except Exception:
                logger.warning("Failed to save captcha debug image", exc_info=True)

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_results_table(self, html: str) -> list[SCOrderRecord]:
        """
        Parse the AJAX response HTML to extract order records.

        Verified column structure (from browser DevTools capture):
            [0] Serial Number
            [1] Diary Number
            [2] Case Number
            [3] Petitioner / Respondent
            [4] Petitioner/Respondent Advocate
            [5] Bench (often empty, class="bt-hide")
            [6] Judgment By (often empty, class="bt-hide")
            [7] ROP — contains <a> link to PDF, link text is the date

        Each <tr> has a data-diary-no attribute.
        PDF URLs are absolute (api.sci.gov.in domain).
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("No results table found in SC AJAX response")
            return []

        records: list[SCOrderRecord] = []
        tbody = table.find("tbody")
        rows = (tbody or table).find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            try:
                # Column indices verified from real AJAX response
                diary_number = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                case_number = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                # Parties: contains <div>PETITIONER</div><div>VS<br>RESPONDENT</div>
                parties_cell = cells[3] if len(cells) > 3 else None
                parties = ""
                if parties_cell:
                    divs = parties_cell.find_all("div")
                    if divs:
                        parts = [d.get_text(strip=True) for d in divs]
                        parties = " ".join(parts)
                    else:
                        parties = parties_cell.get_text(strip=True)

                # ROP column (last data column) has <a> with PDF link
                # The link text IS the date (e.g. "20-02-2026")
                rop_cell = cells[7] if len(cells) > 7 else cells[-1]
                pdf_link = rop_cell.find("a", href=True) if rop_cell else None
                pdf_url = ""
                order_date = None

                if pdf_link:
                    href = pdf_link["href"]
                    if not href.startswith("http"):
                        pdf_url = f"{self._base_url}{href}"
                    else:
                        pdf_url = href
                    # Date is the link text
                    date_text = pdf_link.get_text(strip=True)
                    order_date = self._parse_date(date_text)

                if case_number and pdf_url:
                    records.append(SCOrderRecord(
                        case_number=case_number,
                        diary_number=diary_number,
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
        4. GET with query params (verified via browser DevTools)
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
                answer = await self._solve_math_captcha(image_bytes)
                logger.info(
                    "Captcha attempt %d/%d: solved answer=%d",
                    attempt + 1, self._captcha_max_attempts, answer,
                )

                # Step 4: GET with query params
                # Field names verified from browser DevTools Network tab capture:
                #   from_date, to_date, scid, tok_*, siwp_captcha_value,
                #   es_ajax_request=1, submit=Search,
                #   action=get_daily_order_rop_date, language=en
                params = {
                    **hidden_fields,
                    "from_date": from_date.strftime("%d-%m-%Y"),
                    "to_date": to_date.strftime("%d-%m-%Y"),
                    "siwp_captcha_value": str(answer),
                    "submit": "Search",
                    "action": "get_daily_order_rop_date",
                    "language": "en",
                }

                await self._rate_limit()
                resp = await self._client.get(
                    self._ajax_url,
                    params=params,
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

                # Step 5: Check for captcha rejection (server may return
                # HTTP 200 with an error message instead of 4xx)
                if self._is_captcha_rejection(resp.text):
                    logger.warning(
                        "Captcha answer %d rejected by server (attempt %d/%d). "
                        "Response preview: %s",
                        answer, attempt + 1, self._captcha_max_attempts,
                        resp.text[:200],
                    )
                    last_err = SCCaptchaError(
                        f"Server rejected captcha answer: {answer}"
                    )
                    continue

                # Step 6: Parse results
                records = self._parse_results_table(resp.text)

                if not records:
                    logger.warning(
                        "AJAX response contained no results table. "
                        "Response length=%d, preview: %s",
                        len(resp.text), resp.text[:300],
                    )

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
