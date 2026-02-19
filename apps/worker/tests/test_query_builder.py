"""Tests for vigil.query_builder — build_query() pure function."""

from __future__ import annotations

from datetime import date

import pytest

from vigil.query_builder import build_query

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Entity watch type
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_entity_single_word():
    """Entity: single-word query_terms should be quoted."""
    result = build_query("entity", "Reliance", ["supremecourt"], date(2026, 2, 15))
    assert result == '"Reliance" doctypes:supremecourt fromdate:15-02-2026'


@pytest.mark.unit
def test_entity_multi_word():
    """Entity: multi-word query_terms quoted, multiple courts comma-separated."""
    result = build_query(
        "entity", "Amazon Web Services", ["supremecourt", "delhi"], date(2026, 2, 15)
    )
    assert result == '"Amazon Web Services" doctypes:supremecourt,delhi fromdate:15-02-2026'


@pytest.mark.unit
def test_entity_with_to_date():
    """Entity: todate should appear when to_date is supplied."""
    result = build_query(
        "entity",
        "Reliance Industries",
        ["bombay"],
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert "todate:28-02-2026" in result
    assert '"Reliance Industries"' in result
    assert "doctypes:bombay" in result
    assert "fromdate:01-02-2026" in result


# ---------------------------------------------------------------------------
# Topic watch type
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_topic_single_term():
    """Topic: single word should be bare (no quotes)."""
    result = build_query("topic", "DTAA", ["supremecourt"], date(2026, 1, 1))
    assert result == "DTAA doctypes:supremecourt fromdate:01-01-2026"


@pytest.mark.unit
def test_topic_multi_word_phrase():
    """Topic: multi-word phrase should be quoted."""
    result = build_query("topic", "data protection", ["delhi"], date(2026, 2, 10))
    assert result == '"data protection" doctypes:delhi fromdate:10-02-2026'


@pytest.mark.unit
def test_topic_multiple_terms_with_andd():
    """Topic: multiple separate terms joined with ANDD."""
    result = build_query(
        "topic", "India Mauritius DTAA", ["supremecourt"], date(2026, 2, 15)
    )
    # Each single word should be joined with ANDD
    assert "ANDD" in result
    assert "India" in result
    assert "Mauritius" in result
    assert "DTAA" in result
    assert "doctypes:supremecourt" in result
    assert "fromdate:15-02-2026" in result


@pytest.mark.unit
def test_topic_two_word_terms():
    """Topic: a two-word phrase should be quoted (treated as single phrase)."""
    result = build_query("topic", "transfer pricing", [], date(2026, 3, 1))
    assert result == '"transfer pricing" fromdate:01-03-2026'


# ---------------------------------------------------------------------------
# Act watch type
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_act_basic():
    """Act: query_terms always quoted."""
    result = build_query(
        "act", "Information Technology Act", ["supremecourt"], date(2026, 2, 1)
    )
    assert (
        result
        == '"Information Technology Act" doctypes:supremecourt fromdate:01-02-2026'
    )


@pytest.mark.unit
def test_act_with_year():
    """Act: year and commas preserved inside quotes."""
    result = build_query("act", "Income Tax Act, 1961", [], date(2026, 1, 1))
    assert result == '"Income Tax Act, 1961" fromdate:01-01-2026'


# ---------------------------------------------------------------------------
# Court filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_empty_court_filter():
    """Empty court list: no doctypes: segment in the query."""
    result = build_query("entity", "Tata Motors", [], date(2026, 2, 15))
    assert "doctypes:" not in result
    assert '"Tata Motors"' in result
    assert "fromdate:15-02-2026" in result


@pytest.mark.unit
def test_many_courts():
    """Six courts should produce comma-separated doctypes list."""
    courts = ["supremecourt", "delhi", "bombay", "kolkata", "chennai", "karnataka"]
    result = build_query("entity", "Test Corp", courts, date(2026, 2, 15))
    assert "doctypes:supremecourt,delhi,bombay,kolkata,chennai,karnataka" in result


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_date_format_zero_padding():
    """Dates should be zero-padded: day=5, month=1 -> 05-01."""
    result = build_query("entity", "Test", ["delhi"], date(2026, 1, 5))
    assert "fromdate:05-01-2026" in result


@pytest.mark.unit
def test_date_format_december():
    """December date formatting: 25-12-2025."""
    result = build_query("entity", "Test", ["delhi"], date(2025, 12, 25))
    assert "fromdate:25-12-2025" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_special_characters():
    """Special chars in entity name should be preserved inside quotes."""
    result = build_query(
        "entity", "M/s A.B.C. Pvt. Ltd.", ["delhi"], date(2026, 2, 1)
    )
    assert '"M/s A.B.C. Pvt. Ltd."' in result
    assert "doctypes:delhi" in result
    assert "fromdate:01-02-2026" in result


@pytest.mark.unit
def test_invalid_watch_type_raises():
    """Unknown watch_type should raise ValueError."""
    with pytest.raises(ValueError):
        build_query("invalid_type", "test", ["delhi"], date(2026, 2, 1))
