from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMAnalyticsProposal:
    """A proposed LLM analytics instrumentation."""

    file_path: str
    function_name: str
    rationale: str
    instrumentation_type: str  # "tracing", "token_tracking", "latency"
    code_snippet: str


def extract_llm_analytics_proposals(analysis: dict[str, Any]) -> list[LLMAnalyticsProposal]:
    """Extract LLM analytics proposals from the analysis.

    LLM analytics is a specialized product that tracks AI/ML operations.
    This is only relevant when the codebase contains LLM API calls.
    """
    # LLM analytics suggestions come through the general code_changes
    # and proposed_insights paths. This module handles any LLM-specific
    # proposals that need special treatment.
    #
    # For now, LLM analytics gaps are handled as part of the general
    # missing_events analysis. This module exists as an extension point
    # for future LLM-specific analysis (e.g., checking for @observe
    # decorators, LangSmith tracing, etc.)
    return []
