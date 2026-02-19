"""
Deduplication and match recording.

CRITICAL: This module prevents missed judgments AND duplicate alerts.

LOGIC:
1. For each search result doc:
   - Upsert into judgments table (ON CONFLICT on ik_doc_id).
   - Insert into watch_matches with is_notified=FALSE.
2. Return only NEWLY created matches for notification.
"""

from __future__ import annotations

import logging

from vigil.supabase_client import supabase

logger = logging.getLogger(__name__)


def _map_doc_to_judgment(doc: dict) -> dict | None:
    """Map IK API doc fields to judgments table columns.

    Returns None if the doc is missing the required ``tid`` field.
    """
    tid = doc.get("tid")
    if tid is None:
        logger.warning("Doc missing required 'tid' field, skipping: %s", str(doc)[:200])
        return None
    return {
        "ik_doc_id": tid,
        "title": doc.get("title"),
        "court": doc.get("docsource"),
        "judgment_date": doc.get("publishdate"),
        "headline": doc.get("headline"),
        "num_cites": doc.get("numcites"),
        "doc_size": doc.get("docsize"),
    }


async def process_search_results(
    watch_id: str, results: list[dict]
) -> list[dict]:
    """
    Process IK search results for a given watch.

    Upserts judgments, creates watch_matches, and returns only new matches.

    Args:
        watch_id: UUID of the watch that produced these results.
        results: List of doc dicts from the IK search API response.

    Returns:
        List of newly created watch_match records (for notification).
    """
    if not results:
        return []

    new_matches = []

    for doc in results:
        try:
            judgment_data = _map_doc_to_judgment(doc)
            if judgment_data is None:
                continue

            # Upsert judgment — ON CONFLICT updates and returns the row
            upsert_resp = (
                supabase.table("judgments")
                .upsert(judgment_data, on_conflict="ik_doc_id")
                .execute()
            )

            if not upsert_resp.data:
                continue

            judgment_id = upsert_resp.data[0]["id"]

            # Insert watch_match
            match_data = {
                "watch_id": watch_id,
                "judgment_id": judgment_id,
                "is_notified": False,
                "snippet": doc.get("headline"),
            }

            match_resp = (
                supabase.table("watch_matches")
                .insert(match_data)
                .execute()
            )

            if match_resp.data:
                new_matches.extend(match_resp.data)

        except Exception:
            logger.error(
                "Error processing doc %s for watch %s",
                doc.get("tid"),
                watch_id,
                exc_info=True,
            )
            continue

    return new_matches
