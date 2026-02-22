"""
Tests for process_sc_orders() in vigil.matcher.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from vigil.matcher import process_sc_orders
from vigil.sc_client import SCOrderRecord
from vigil.sc_matcher import MatchResult


# ── Helpers ──────────────────────────────────────────────


def _make_order(
    case_number: str = "SLP(C) No. 12345/2025",
    diary_number: str = "12345-2025",
    parties: str = "Amazon Web Services Inc. vs Union of India",
) -> SCOrderRecord:
    return SCOrderRecord(
        case_number=case_number,
        diary_number=diary_number,
        parties=parties,
        order_date=date(2026, 2, 21),
        pdf_url="https://www.sci.gov.in/pdf/order.pdf",
    )


def _make_match_result(
    is_match: bool = True,
    relevance_score: float = 0.9,
    snippet: str = "...test snippet...",
) -> MatchResult:
    return MatchResult(
        is_match=is_match,
        relevance_score=relevance_score,
        matched_terms=["test"],
        snippet=snippet,
    )


# ── Tests ────────────────────────────────────────────────


class TestProcessScOrders:
    async def test_upserts_judgment_and_creates_match(self, patch_supabase):
        watch_id = "w1"
        order = _make_order()
        match_result = _make_match_result()
        full_text = "Order text here."

        # Mock upsert response (judgment created)
        upsert_resp = MagicMock(data=[{"id": "j1"}])
        # Mock insert response (match created)
        insert_resp = MagicMock(data=[{"id": "m1", "watch_id": watch_id, "judgment_id": "j1"}])

        patch_supabase.table.return_value.execute.side_effect = [
            upsert_resp,
            insert_resp,
        ]

        new_matches = await process_sc_orders(watch_id, [(order, match_result, full_text)])

        assert len(new_matches) == 1
        assert new_matches[0]["judgment_id"] == "j1"

        # First upsert is for judgments, second is for watch_matches
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        judgment_data = upsert_calls[0][0][0]
        assert judgment_data["source"] == "sc_website"
        assert judgment_data["sc_case_number"] == "SLP(C) No. 12345/2025"
        assert judgment_data["ik_doc_id"] is None
        assert "Amazon Web Services" in judgment_data["title"]
        assert judgment_data["external_url"] == "https://www.sci.gov.in/pdf/order.pdf"
        assert judgment_data["full_text"] == "Order text here."

    async def test_empty_orders_returns_empty(self, patch_supabase):
        new_matches = await process_sc_orders("w1", [])
        assert new_matches == []

    async def test_upsert_returns_no_data_skips_match(self, patch_supabase):
        order = _make_order()
        match_result = _make_match_result()

        patch_supabase.table.return_value.execute.return_value = MagicMock(data=[])

        new_matches = await process_sc_orders("w1", [(order, match_result, "")])
        assert new_matches == []

    async def test_exception_during_processing_continues(self, patch_supabase):
        order1 = _make_order(case_number="Case 1")
        order2 = _make_order(case_number="Case 2")
        match_result = _make_match_result()

        # First order raises, second succeeds
        patch_supabase.table.return_value.execute.side_effect = [
            Exception("DB error"),
            MagicMock(data=[{"id": "j2"}]),
            MagicMock(data=[{"id": "m2", "watch_id": "w1", "judgment_id": "j2"}]),
        ]

        new_matches = await process_sc_orders(
            "w1",
            [(order1, match_result, ""), (order2, match_result, "")],
        )
        # Only second order's match should succeed
        assert len(new_matches) == 1

    async def test_full_text_capped_at_100k(self, patch_supabase):
        order = _make_order()
        match_result = _make_match_result()
        long_text = "x" * 200_000

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j1"}]),
            MagicMock(data=[{"id": "m1"}]),
        ]

        await process_sc_orders("w1", [(order, match_result, long_text)])

        # First upsert is for judgments
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        judgment_data = upsert_calls[0][0][0]
        assert len(judgment_data["full_text"]) == 100_000

    async def test_snippet_capped_at_500_chars(self, patch_supabase):
        order = _make_order()
        long_snippet = "s" * 1000
        match_result = _make_match_result(snippet=long_snippet)

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j1"}]),
            MagicMock(data=[{"id": "m1"}]),
        ]

        await process_sc_orders("w1", [(order, match_result, "")])

        # Second upsert is for watch_matches
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        match_data = upsert_calls[1][0][0]
        assert len(match_data["snippet"]) == 500

    async def test_judgment_date_mapped_correctly(self, patch_supabase):
        order = _make_order()
        match_result = _make_match_result()

        patch_supabase.table.return_value.execute.side_effect = [
            MagicMock(data=[{"id": "j1"}]),
            MagicMock(data=[{"id": "m1"}]),
        ]

        await process_sc_orders("w1", [(order, match_result, "")])

        # First upsert is for judgments
        upsert_calls = patch_supabase.table.return_value.upsert.call_args_list
        judgment_data = upsert_calls[0][0][0]
        assert judgment_data["judgment_date"] == "2026-02-21"
        assert judgment_data["court"] == "Supreme Court of India"
