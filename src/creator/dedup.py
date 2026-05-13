from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# Similarity threshold for considering two names as duplicates
SIMILARITY_THRESHOLD = 0.8


def is_duplicate_insight(
    proposed_name: str,
    existing_insights: list[dict[str, Any]],
) -> bool:
    """Check if a proposed insight name is too similar to an existing one."""
    proposed_lower = proposed_name.lower().strip()

    for insight in existing_insights:
        existing_name = (insight.get("name") or "").lower().strip()
        if not existing_name:
            continue

        # Exact match
        if proposed_lower == existing_name:
            logger.info(f"Duplicate insight detected (exact match): '{proposed_name}'")
            return True

        # Fuzzy match
        similarity = SequenceMatcher(None, proposed_lower, existing_name).ratio()
        if similarity >= SIMILARITY_THRESHOLD:
            logger.info(
                f"Duplicate insight detected (similarity={similarity:.2f}): '{proposed_name}' ≈ '{insight.get('name')}'"
            )
            return True

    return False


def is_duplicate_flag(
    proposed_key: str,
    existing_flags: list[dict[str, Any]],
) -> bool:
    """Check if a proposed feature flag key already exists."""
    proposed_lower = proposed_key.lower().strip()

    for flag in existing_flags:
        existing_key = (flag.get("key") or "").lower().strip()
        if proposed_lower == existing_key:
            logger.info(f"Duplicate feature flag detected: '{proposed_key}'")
            return True

    return False


def is_duplicate_dashboard(
    proposed_name: str,
    existing_dashboards: list[dict[str, Any]],
) -> bool:
    """Check if a proposed dashboard name is too similar to an existing one."""
    proposed_lower = proposed_name.lower().strip()

    for dashboard in existing_dashboards:
        existing_name = (dashboard.get("name") or "").lower().strip()
        if not existing_name:
            continue

        if proposed_lower == existing_name:
            logger.info(f"Duplicate dashboard detected (exact match): '{proposed_name}'")
            return True

        similarity = SequenceMatcher(None, proposed_lower, existing_name).ratio()
        if similarity >= SIMILARITY_THRESHOLD:
            logger.info(
                f"Duplicate dashboard detected (similarity={similarity:.2f}): "
                f"'{proposed_name}' ≈ '{dashboard.get('name')}'"
            )
            return True

    return False
