"""
Constructs Indian Kanoon formInput strings.

RULES:
1. Entity names ALWAYS in quotes for exact phrase matching.
2. Multi-word topic terms in quotes. Single words left bare.
3. Court filter appended as doctypes: parameter.
4. fromdate: ALWAYS included — set to last_polled_at or creation date.
5. Date format: DD-MM-YYYY (Indian Kanoon's expected format).
"""

from __future__ import annotations

from datetime import date


def build_query(
    watch_type: str,
    query_terms: str,
    court_filter: list[str],
    from_date: date,
    to_date: date | None = None,
) -> str:
    """
    Build a formInput query string for the IK search API.

    Args:
        watch_type: One of 'entity', 'topic', 'act'.
        query_terms: The raw search terms from the watch config.
        court_filter: List of court codes (e.g., ['supremecourt', 'delhi']).
        from_date: Minimum date for results.
        to_date: Optional maximum date for results.

    Returns:
        Formatted formInput string ready for the IK API.
    """
    if watch_type not in ("entity", "topic", "act"):
        raise ValueError(f"Unknown watch_type: {watch_type!r}")

    if watch_type in ("entity", "act"):
        # Always wrap in quotes for exact phrase matching
        terms_part = f'"{query_terms.strip()}"'
    else:
        # Topic: split into terms, join with ANDD
        stripped = query_terms.strip()
        if "," in stripped:
            # Comma-separated terms: each piece is a term
            raw = [t.strip() for t in stripped.split(",") if t.strip()]
            terms_part = " ANDD ".join(
                f'"{t}"' if " " in t else t for t in raw
            )
        else:
            words = stripped.split()
            if len(words) <= 2:
                # 1-2 words: single term (quoted if multi-word)
                terms_part = f'"{stripped}"' if len(words) > 1 else stripped
            else:
                # 3+ words: each word is a separate ANDD term
                terms_part = " ANDD ".join(words)

    parts = [terms_part]
    if court_filter:
        parts.append(f"doctypes:{','.join(court_filter)}")
    parts.append(f"fromdate:{from_date.strftime('%d-%m-%Y')}")
    if to_date is not None:
        parts.append(f"todate:{to_date.strftime('%d-%m-%Y')}")
    return " ".join(parts)
