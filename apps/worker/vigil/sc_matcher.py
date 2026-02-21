"""
Local text matching for SC daily orders.

Unlike IK search results (which are pre-filtered by query),
SC daily orders are a full dump of all orders for a date range.
This module determines which orders are relevant to each watch.

MATCHING STRATEGY:
1. Phase 1 (fast): Check if query_terms appear in parties/case_number
   from the HTML table (no PDF download needed).
2. Phase 2 (slower): For potential matches, download PDF and search
   full text for query_terms.
3. Relevance scoring: count of term occurrences, weighted by location
   (title match > body match).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vigil.sc_client import SCOrderRecord


@dataclass
class MatchResult:
    """Result of matching an SC order against a watch."""
    is_match: bool
    relevance_score: float
    matched_terms: list[str] = field(default_factory=list)
    snippet: str = ""


def match_order_against_watch(
    order: SCOrderRecord,
    watch: dict,
    full_text: str | None = None,
) -> MatchResult:
    """
    Determine if an SC order matches a watch's query_terms.

    Args:
        order: Parsed SC order record (case number, parties, etc.)
        watch: Watch dict with watch_type, query_terms, etc.
        full_text: Extracted PDF text (None if not yet downloaded)

    Strategy by watch_type:
        - 'entity': Exact phrase match in parties + full_text
        - 'topic': All terms (AND logic) must appear
        - 'act': Exact phrase match of act name
    """
    query_terms = watch.get("query_terms", "").strip()
    watch_type = watch.get("watch_type", "entity")

    if not query_terms:
        return MatchResult(is_match=False, relevance_score=0.0)

    searchable_parts = [
        order.parties or "",
        order.case_number or "",
    ]
    if full_text:
        searchable_parts.append(full_text)
    searchable = " ".join(searchable_parts).lower()

    if watch_type == "entity":
        return _match_entity(query_terms, searchable, order)
    elif watch_type == "topic":
        return _match_topic(query_terms, searchable, order)
    elif watch_type == "act":
        return _match_act(query_terms, searchable, order)
    else:
        return MatchResult(is_match=False, relevance_score=0.0)


def needs_pdf_download(order: SCOrderRecord, watches: list[dict]) -> bool:
    """
    Determine if we need to download the PDF for deeper matching.

    Quick check: if entity query_terms already appear in parties,
    we have a match without the PDF. Otherwise, need full text.

    Returns True if any watch requires full_text for matching.
    """
    parties_lower = (order.parties or "").lower()
    case_lower = (order.case_number or "").lower()
    combined = f"{parties_lower} {case_lower}"

    for watch in watches:
        watch_type = watch.get("watch_type", "entity")
        terms = watch.get("query_terms", "").strip().lower()

        if not terms:
            continue

        if watch_type == "entity" and terms in combined:
            # Entity match found in parties — no PDF needed for THIS watch
            continue
        else:
            # Need full text for topic/act matching, or entity not in parties
            return True

    return False


def _match_entity(
    query_terms: str, searchable: str, order: SCOrderRecord
) -> MatchResult:
    """Entity matching: exact phrase in parties or full text."""
    phrase = query_terms.lower()
    in_parties = phrase in (order.parties or "").lower()
    in_text = phrase in searchable

    if not in_text:
        return MatchResult(is_match=False, relevance_score=0.0)

    score = 0.9 if in_parties else 0.5
    snippet = _extract_snippet(searchable, phrase)
    return MatchResult(
        is_match=True,
        relevance_score=score,
        matched_terms=[query_terms],
        snippet=snippet,
    )


def _match_topic(
    query_terms: str, searchable: str, order: SCOrderRecord
) -> MatchResult:
    """Topic matching: all terms must appear (AND logic, matching query_builder.py)."""
    if "," in query_terms:
        terms = [t.strip().lower() for t in query_terms.split(",") if t.strip()]
    else:
        terms = query_terms.lower().split()

    if not terms:
        return MatchResult(is_match=False, relevance_score=0.0)

    matched = [t for t in terms if t in searchable]

    if len(matched) < len(terms):
        return MatchResult(is_match=False, relevance_score=0.0)

    total_count = sum(searchable.count(t) for t in matched)
    score = min(0.3 + (total_count * 0.05), 1.0)
    snippet = _extract_snippet(searchable, matched[0])
    return MatchResult(
        is_match=True,
        relevance_score=score,
        matched_terms=matched,
        snippet=snippet,
    )


def _match_act(
    query_terms: str, searchable: str, order: SCOrderRecord
) -> MatchResult:
    """Act matching: exact phrase match of act name."""
    phrase = query_terms.lower()
    if phrase not in searchable:
        return MatchResult(is_match=False, relevance_score=0.0)

    count = searchable.count(phrase)
    score = min(0.4 + (count * 0.1), 1.0)
    snippet = _extract_snippet(searchable, phrase)
    return MatchResult(
        is_match=True,
        relevance_score=score,
        matched_terms=[query_terms],
        snippet=snippet,
    )


def _extract_snippet(text: str, term: str, context_chars: int = 200) -> str:
    """Extract a text snippet around the first occurrence of term."""
    idx = text.find(term)
    if idx == -1:
        return ""
    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(term) + context_chars // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
