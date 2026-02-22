"""Tests for vigil/matcher.py — _map_doc_to_judgment() and process_search_results()."""

from unittest.mock import MagicMock

import pytest

from vigil.matcher import _map_doc_to_judgment, process_search_results


# ---------------------------------------------------------------------------
# _map_doc_to_judgment — field mapping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMapDocToJudgment:
    """Tests for the _map_doc_to_judgment helper."""

    def test_maps_all_fields(self, ik_search_response_single):
        """All IK doc fields should be mapped to judgment columns."""
        doc = ik_search_response_single["docs"][0]
        result = _map_doc_to_judgment(doc)

        assert result["ik_doc_id"] == doc["tid"]
        assert result["title"] == doc["title"]
        assert result["court"] == doc["docsource"]
        assert result["judgment_date"] == doc["publishdate"]
        assert result["headline"] == doc["headline"]
        assert result["num_cites"] == doc["numcites"]
        assert result["doc_size"] == doc["docsize"]

    def test_missing_tid_returns_none(self):
        """Doc without 'tid' field -> returns None."""
        doc = {
            "title": "Some Judgment",
            "docsource": "Delhi HC",
        }
        result = _map_doc_to_judgment(doc)
        assert result is None

    def test_tid_none_returns_none(self):
        """Doc with tid=None -> returns None."""
        doc = {"tid": None, "title": "X"}
        result = _map_doc_to_judgment(doc)
        assert result is None

    def test_missing_optional_fields(self):
        """None values should be preserved in the mapping."""
        doc = {
            "tid": 999,
            "title": "Judgment with Missing Fields",
            "docsource": "Supreme Court of India",
            "headline": None,
            "publishdate": None,
            "numcites": 0,
            "docsize": None,
        }
        result = _map_doc_to_judgment(doc)

        assert result["headline"] is None
        assert result["doc_size"] is None
        assert result["judgment_date"] is None
        assert result["num_cites"] == 0


# ---------------------------------------------------------------------------
# process_search_results — empty input
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyResults:
    """Empty results should short-circuit with no DB calls."""

    async def test_empty_list(self, patch_supabase):
        """results=[] -> no DB calls, returns []."""
        result = await process_search_results("w-1", [])

        assert result == []
        patch_supabase.table.assert_not_called()


# ---------------------------------------------------------------------------
# process_search_results — happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNewJudgmentAndMatch:
    """Tests for the new-judgment + new-match path."""

    async def test_new_judgment_inserted(
        self, patch_supabase, ik_search_response_single
    ):
        """1 doc -> judgment upserted, match created, returns 1 match."""
        docs = ik_search_response_single["docs"]
        judgment_row = {"id": "j-new-1", "ik_doc_id": docs[0]["tid"]}
        match_row = {
            "id": "wm-1",
            "watch_id": "w-1",
            "judgment_id": "j-new-1",
            "is_notified": False,
        }

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[judgment_row]),  # upsert judgment
            MagicMock(data=[match_row]),  # insert match
        ]

        result = await process_search_results("w-1", docs)

        assert len(result) == 1
        assert result[0]["id"] == "wm-1"
        patch_supabase.table.assert_any_call("judgments")
        patch_supabase.table.assert_any_call("watch_matches")

    async def test_judgment_fields_mapped(
        self, patch_supabase, ik_search_response_single
    ):
        """tid->ik_doc_id, title->title, docsource->court, etc."""
        docs = ik_search_response_single["docs"]
        doc = docs[0]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-1"}]),
            MagicMock(data=[{"id": "wm-1"}]),
        ]

        await process_search_results("w-1", docs)

        # First upsert call is for judgments, second is for watch_matches
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        inserted = upsert_calls[0][0][0]
        assert inserted["ik_doc_id"] == doc["tid"]
        assert inserted["title"] == doc["title"]
        assert inserted["court"] == doc["docsource"]
        assert inserted["headline"] == doc["headline"]
        assert inserted["num_cites"] == doc["numcites"]
        assert inserted["doc_size"] == doc["docsize"]

    async def test_watch_match_fields(
        self, patch_supabase, ik_search_response_single
    ):
        """watch_id set, is_notified=False, snippet from headline."""
        docs = ik_search_response_single["docs"]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-1"}]),
            MagicMock(data=[{"id": "wm-1"}]),
        ]

        await process_search_results("w-1", docs)

        # Second upsert call is for watch_matches
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        match_data = upsert_calls[1][0][0]
        assert match_data["watch_id"] == "w-1"
        assert match_data["is_notified"] is False
        assert match_data["snippet"] == docs[0]["headline"]


# ---------------------------------------------------------------------------
# process_search_results — deduplication
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeduplication:
    """Tests for dedup: upsert conflict and match conflict paths."""

    async def test_upsert_conflict_skips(
        self, patch_supabase, ik_search_response_single
    ):
        """Upsert returns empty (conflict) -> skip, no match insert."""
        docs = ik_search_response_single["docs"]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[]),  # upsert conflict
        ]

        result = await process_search_results("w-1", docs)

        assert result == []

    async def test_match_insert_conflict(
        self, patch_supabase, ik_search_response_single
    ):
        """Match insert returns empty (duplicate) -> not in results."""
        docs = ik_search_response_single["docs"]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-1"}]),  # upsert ok
            MagicMock(data=[]),  # insert conflict
        ]

        result = await process_search_results("w-1", docs)

        assert result == []

    async def test_idempotency(
        self, patch_supabase, ik_search_response_single
    ):
        """Process same results twice -> second call returns 0 new matches."""
        docs = ik_search_response_single["docs"]

        # First call: new judgment + new match
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-1"}]),
            MagicMock(data=[{"id": "wm-1"}]),
        ]
        first = await process_search_results("w-1", docs)
        assert len(first) == 1

        # Second call: upsert conflict
        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[]),
        ]
        second = await process_search_results("w-1", docs)
        assert len(second) == 0


# ---------------------------------------------------------------------------
# process_search_results — multiple docs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultipleResults:
    """Tests for batch processing with mixed new/existing docs."""

    async def test_mixed_new_and_existing(
        self, patch_supabase, ik_search_response_multiple
    ):
        """3 docs: doc 1 new, doc 2 conflict, doc 3 new -> 2 matches."""
        docs = ik_search_response_multiple["docs"]

        patch_supabase.table.return_value.execute.side_effect = [
            # Doc 1: new judgment + new match
            MagicMock(data=[{"id": "j-1"}]),
            MagicMock(data=[{"id": "wm-1"}]),
            # Doc 2: upsert conflict -> skip
            MagicMock(data=[]),
            # Doc 3: new judgment + new match
            MagicMock(data=[{"id": "j-3"}]),
            MagicMock(data=[{"id": "wm-3"}]),
        ]

        result = await process_search_results("w-1", docs)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# process_search_results — error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    """Tests for graceful error handling."""

    async def test_supabase_error_returns_empty(
        self, patch_supabase, ik_search_response_single
    ):
        """Supabase raises -> logs error, returns [] (no crash)."""
        docs = ik_search_response_single["docs"]

        patch_supabase.table.return_value.execute.side_effect = Exception(
            "Supabase connection error"
        )

        result = await process_search_results("w-1", docs)

        assert result == []

    async def test_missing_tid_skipped_gracefully(self, patch_supabase):
        """Doc with no tid -> skipped, valid doc still processed."""
        docs = [
            {"title": "No TID Doc", "docsource": "Delhi HC"},
            {"tid": 12345, "title": "Good Doc", "docsource": "SC"},
        ]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-1"}]),  # upsert for good doc
            MagicMock(data=[{"id": "wm-1"}]),  # match for good doc
        ]

        result = await process_search_results("w-1", docs)

        # Only the valid doc should produce a match
        assert len(result) == 1

    async def test_missing_optional_fields_preserved(self, patch_supabase):
        """Doc with headline=None -> inserted with None."""
        docs = [
            {
                "tid": 999,
                "title": "Judgment with Missing Fields",
                "docsource": "Supreme Court of India",
                "publishdate": "2026-02-17",
                "headline": None,
                "numcites": 0,
                "docsize": None,
            }
        ]

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j-999"}]),
            MagicMock(data=[{"id": "wm-999"}]),
        ]

        await process_search_results("w-1", docs)

        # First upsert call is for judgments
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        data = upsert_calls[0][0][0]
        assert data["headline"] is None
        assert data["doc_size"] is None


# ---------------------------------------------------------------------------
# _map_doc_to_judgment — sanitization (HTML stripping + date validation)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSanitization:
    """Tests for HTML stripping and date validation in _map_doc_to_judgment."""

    # -- HTML stripping: title --

    def test_title_html_tags_stripped(self):
        doc = {"tid": 1, "title": "Department Of <b>Income</b> <b>Tax</b>", "docsource": "SC"}
        result = _map_doc_to_judgment(doc)
        assert result["title"] == "Department Of Income Tax"

    def test_title_nested_tags_stripped(self):
        doc = {"tid": 2, "title": "<em><b>Test</b></em> Judgment"}
        result = _map_doc_to_judgment(doc)
        assert result["title"] == "Test Judgment"

    def test_title_no_html_unchanged(self):
        doc = {"tid": 3, "title": "Clean Title vs Another Party"}
        result = _map_doc_to_judgment(doc)
        assert result["title"] == "Clean Title vs Another Party"

    def test_title_none_preserved(self):
        doc = {"tid": 4, "title": None}
        result = _map_doc_to_judgment(doc)
        assert result["title"] is None

    def test_title_whitespace_normalized(self):
        doc = {"tid": 5, "title": "A  <b>B</b>  C"}
        result = _map_doc_to_judgment(doc)
        assert result["title"] == "A B C"

    # -- HTML stripping: court --

    def test_court_html_tags_stripped(self):
        doc = {"tid": 6, "docsource": "<b>Delhi</b> High Court"}
        result = _map_doc_to_judgment(doc)
        assert result["court"] == "Delhi High Court"

    def test_court_none_preserved(self):
        doc = {"tid": 7, "docsource": None}
        result = _map_doc_to_judgment(doc)
        assert result["court"] is None

    # -- Headline NOT stripped --

    def test_headline_html_preserved(self):
        doc = {"tid": 8, "headline": "...cloud <b>Amazon</b> services..."}
        result = _map_doc_to_judgment(doc)
        assert "<b>Amazon</b>" in result["headline"]

    # -- Date validation --

    def test_valid_date_passes_through(self):
        doc = {"tid": 10, "publishdate": "2024-03-15"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] == "2024-03-15"

    def test_future_year_rejected(self):
        doc = {"tid": 11, "publishdate": "3015-03-30"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_garbled_year_rejected(self):
        doc = {"tid": 12, "publishdate": "6648-09-02"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_slightly_future_year_rejected(self):
        doc = {"tid": 13, "publishdate": "2205-10-03"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_current_year_accepted(self):
        from datetime import datetime

        current_year = datetime.now().year
        doc = {"tid": 14, "publishdate": f"{current_year}-01-15"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] == f"{current_year}-01-15"

    def test_date_none_preserved(self):
        doc = {"tid": 15, "publishdate": None}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_empty_string_date_rejected(self):
        doc = {"tid": 16, "publishdate": ""}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_non_numeric_date_rejected(self):
        doc = {"tid": 17, "publishdate": "not-a-date"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] is None

    def test_old_date_accepted(self):
        doc = {"tid": 18, "publishdate": "1950-01-26"}
        result = _map_doc_to_judgment(doc)
        assert result["judgment_date"] == "1950-01-26"
