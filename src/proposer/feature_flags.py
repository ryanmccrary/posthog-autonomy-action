from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FeatureFlagProposal:
    """A proposed PostHog feature flag."""

    key: str
    name: str
    rationale: str
    rollout_percentage: int = 0


def extract_feature_flag_proposal(
    analysis: dict[str, Any],
    flags_enabled: bool = False,
) -> FeatureFlagProposal | None:
    """Extract feature flag proposal from the LLM analysis.

    Only returns a proposal if feature flags are enabled in the config.
    """
    if not flags_enabled:
        return None

    flag_data = analysis.get("proposed_feature_flag")
    if not flag_data:
        return None

    return FeatureFlagProposal(
        key=flag_data.get("key", ""),
        name=flag_data.get("name", ""),
        rationale=flag_data.get("rationale", ""),
        rollout_percentage=flag_data.get("rollout_percentage", 0),
    )
