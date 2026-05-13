from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InsightProposal:
    """A proposed PostHog insight."""

    name: str
    description: str
    query_type: str  # trends, funnels, retention
    query_hint: str
    rationale: str


@dataclass
class DashboardProposal:
    """A proposed PostHog dashboard."""

    name: str
    description: str
    insight_indices: list[int] = field(default_factory=list)


def extract_insight_proposals(analysis: dict[str, Any], naming_prefix: str = "") -> list[InsightProposal]:
    """Extract insight proposals from the LLM analysis."""
    proposals: list[InsightProposal] = []

    for item in analysis.get("proposed_insights", []):
        name = item.get("name", "")
        if naming_prefix and not name.startswith(naming_prefix):
            name = f"{naming_prefix}{name}"

        proposals.append(
            InsightProposal(
                name=name,
                description=item.get("description", ""),
                query_type=item.get("query_type", "trends"),
                query_hint=item.get("query_hint", ""),
                rationale=item.get("rationale", ""),
            )
        )

    return proposals


def extract_dashboard_proposal(analysis: dict[str, Any], naming_prefix: str = "") -> DashboardProposal | None:
    """Extract dashboard proposal from the LLM analysis."""
    dashboard = analysis.get("proposed_dashboard")
    if not dashboard:
        return None

    name = dashboard.get("name", "")
    if naming_prefix and not name.startswith(naming_prefix):
        name = f"{naming_prefix}{name}"

    return DashboardProposal(
        name=name,
        description=dashboard.get("description", ""),
        insight_indices=dashboard.get("include_insights", []),
    )
