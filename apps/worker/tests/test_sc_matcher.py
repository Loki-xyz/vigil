"""
Tests for vigil.sc_matcher — local text matching for SC daily orders.
"""

from __future__ import annotations

from datetime import date

import pytest

from vigil.sc_client import SCOrderRecord
from vigil.sc_matcher import (
    MatchResult,
    _extract_snippet,
    match_order_against_watch,
    needs_pdf_download,
)


# ── Helpers ──────────────────────────────────────────────


def _make_order(
    case_number: str = "SLP(C) No. 12345/2025",
    diary_number: str = "12345-2025",
    parties: str = "Amazon Web Services Inc. vs Union of India",
    order_date: date | None = date(2026, 2, 21),
    pdf_url: str = "https://www.sci.gov.in/pdf/order.pdf",
) -> SCOrderRecord:
    return SCOrderRecord(
        case_number=case_number,
        diary_number=diary_number,
        parties=parties,
        order_date=order_date,
        pdf_url=pdf_url,
    )


def _make_watch(
    watch_type: str = "entity",
    query_terms: str = "Amazon Web Services",
    court_filter: list[str] | None = None,
) -> dict:
    return {
        "id": "w1",
        "watch_type": watch_type,
        "query_terms": query_terms,
        "court_filter": court_filter or ["supremecourt"],
    }


# ── Entity Matching ──────────────────────────────────────


class TestMatchEntity:
    def test_match_in_parties(self):
        order = _make_order(parties="Amazon Web Services Inc. vs CIT")
        watch = _make_watch(watch_type="entity", query_terms="Amazon Web Services")
        result = match_order_against_watch(order, watch)
        assert result.is_match is True
        assert result.relevance_score == 0.9  # In parties = high relevance
        assert "Amazon Web Services" in result.matched_terms

    def test_match_in_full_text_not_parties(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="entity", query_terms="cloud computing")
        full_text = "This order discusses cloud computing services."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is True
        assert result.relevance_score == 0.5  # In body = lower relevance

    def test_no_match(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="entity", query_terms="Reliance Industries")
        result = match_order_against_watch(order, watch)
        assert result.is_match is False
        assert result.relevance_score == 0.0

    def test_case_insensitive(self):
        order = _make_order(parties="AMAZON WEB SERVICES vs CIT")
        watch = _make_watch(watch_type="entity", query_terms="amazon web services")
        result = match_order_against_watch(order, watch)
        assert result.is_match is True

    def test_empty_query_terms(self):
        order = _make_order()
        watch = _make_watch(watch_type="entity", query_terms="")
        result = match_order_against_watch(order, watch)
        assert result.is_match is False


# ── Topic Matching ───────────────────────────────────────


class TestMatchTopic:
    def test_all_terms_present(self):
        order = _make_order(parties="Some Party vs Union")
        watch = _make_watch(watch_type="topic", query_terms="India Mauritius DTAA")
        full_text = "India and Mauritius have a DTAA agreement."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is True
        assert set(result.matched_terms) == {"india", "mauritius", "dtaa"}

    def test_partial_terms_no_match(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="topic", query_terms="India Mauritius DTAA")
        full_text = "India has many bilateral treaties."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is False

    def test_comma_separated_terms(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="topic", query_terms="transfer pricing, cloud services")
        full_text = "Transfer pricing norms apply to cloud services."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is True

    def test_no_full_text_no_match(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="topic", query_terms="patent infringement")
        result = match_order_against_watch(order, watch, full_text=None)
        assert result.is_match is False


# ── Act Matching ─────────────────────────────────────────


class TestMatchAct:
    def test_act_in_full_text(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="act", query_terms="Information Technology Act")
        full_text = "The Information Technology Act, 2000 governs..."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is True

    def test_act_not_found(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="act", query_terms="Patent Act")
        full_text = "This order discusses copyright issues."
        result = match_order_against_watch(order, watch, full_text=full_text)
        assert result.is_match is False

    def test_act_in_parties(self):
        order = _make_order(parties="In Re: Information Technology Act compliance")
        watch = _make_watch(watch_type="act", query_terms="Information Technology Act")
        result = match_order_against_watch(order, watch)
        assert result.is_match is True

    def test_relevance_increases_with_mentions(self):
        order = _make_order(parties="X vs Y")
        watch = _make_watch(watch_type="act", query_terms="income tax act")

        # Single mention
        text1 = "Income Tax Act is referenced here."
        result1 = match_order_against_watch(order, watch, full_text=text1)

        # Multiple mentions
        text2 = "Income Tax Act is referenced. Under Income Tax Act Section 80."
        result2 = match_order_against_watch(order, watch, full_text=text2)

        assert result2.relevance_score > result1.relevance_score


# ── Unknown Watch Type ───────────────────────────────────


class TestUnknownWatchType:
    def test_unknown_type_no_match(self):
        order = _make_order()
        watch = _make_watch(watch_type="unknown", query_terms="something")
        result = match_order_against_watch(order, watch)
        assert result.is_match is False


# ── PDF Download Decision ────────────────────────────────


class TestNeedsPdfDownload:
    def test_entity_in_parties_no_pdf_needed(self):
        order = _make_order(parties="Amazon Web Services vs CIT")
        watches = [_make_watch(watch_type="entity", query_terms="Amazon Web Services")]
        assert needs_pdf_download(order, watches) is False

    def test_entity_not_in_parties_needs_pdf(self):
        order = _make_order(parties="X vs Y")
        watches = [_make_watch(watch_type="entity", query_terms="Reliance")]
        assert needs_pdf_download(order, watches) is True

    def test_topic_always_needs_pdf(self):
        order = _make_order(parties="X vs Y")
        watches = [_make_watch(watch_type="topic", query_terms="transfer pricing")]
        assert needs_pdf_download(order, watches) is True

    def test_act_always_needs_pdf(self):
        order = _make_order(parties="X vs Y")
        watches = [_make_watch(watch_type="act", query_terms="Patent Act")]
        assert needs_pdf_download(order, watches) is True

    def test_mixed_watches_entity_match_plus_topic(self):
        order = _make_order(parties="Amazon Web Services vs CIT")
        watches = [
            _make_watch(watch_type="entity", query_terms="Amazon Web Services"),
            _make_watch(watch_type="topic", query_terms="transfer pricing"),
        ]
        # Topic watch needs PDF even though entity doesn't
        assert needs_pdf_download(order, watches) is True

    def test_empty_query_terms_no_pdf(self):
        order = _make_order()
        watches = [_make_watch(watch_type="entity", query_terms="")]
        assert needs_pdf_download(order, watches) is False


# ── Snippet Extraction ───────────────────────────────────


class TestExtractSnippet:
    def test_term_at_start(self):
        snippet = _extract_snippet("hello world", "hello", context_chars=20)
        assert "hello" in snippet

    def test_term_in_middle(self):
        text = "a" * 100 + "target" + "b" * 100
        snippet = _extract_snippet(text, "target", context_chars=40)
        assert "target" in snippet
        assert snippet.startswith("...")
        assert snippet.endswith("...")

    def test_term_not_found(self):
        snippet = _extract_snippet("hello world", "missing")
        assert snippet == ""
