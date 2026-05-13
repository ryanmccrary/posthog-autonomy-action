from __future__ import annotations

import logging
from typing import Any

from src.creator.dedup import is_duplicate_dashboard, is_duplicate_flag, is_duplicate_insight
from src.posthog_client import PostHogClient
from src.proposer.analytics import DashboardProposal, InsightProposal
from src.proposer.feature_flags import FeatureFlagProposal

logger = logging.getLogger(__name__)


def create_insights(
    client: PostHogClient,
    proposals: list[InsightProposal],
    existing_insights: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create insights from proposals, skipping duplicates. Returns created insight data."""
    created: list[dict[str, Any]] = []

    for proposal in proposals:
        if is_duplicate_insight(proposal.name, existing_insights):
            logger.info(f"Skipping duplicate insight: {proposal.name}")
            continue

        try:
            # Build a basic query based on the query type hint
            query = _build_query_from_hint(proposal.query_type, proposal.query_hint)

            insight = client.create_insight(
                name=proposal.name,
                description=f"{proposal.description}\n\nRationale: {proposal.rationale}",
                query=query,
            )
            created.append(insight)
            logger.info(f"Created insight: {proposal.name} (ID: {insight.get('id')})")
        except Exception as e:
            logger.error(f"Failed to create insight '{proposal.name}': {e}")

    return created


def create_dashboard(
    client: PostHogClient,
    proposal: DashboardProposal,
    insight_ids: list[int],
    existing_dashboards: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Create a dashboard from a proposal, adding the given insights as tiles."""
    if is_duplicate_dashboard(proposal.name, existing_dashboards):
        logger.info(f"Skipping duplicate dashboard: {proposal.name}")
        return None

    try:
        dashboard = client.create_dashboard(
            name=proposal.name,
            description=proposal.description,
        )
        dashboard_id = dashboard.get("id")

        # Add insights to the dashboard
        for insight_id in insight_ids:
            try:
                client.add_insight_to_dashboard(dashboard_id, insight_id)
            except Exception as e:
                logger.error(f"Failed to add insight {insight_id} to dashboard {dashboard_id}: {e}")

        logger.info(f"Created dashboard: {proposal.name} (ID: {dashboard_id})")
        return dashboard
    except Exception as e:
        logger.error(f"Failed to create dashboard '{proposal.name}': {e}")
        return None


def create_feature_flag(
    client: PostHogClient,
    proposal: FeatureFlagProposal,
    existing_flags: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Create a feature flag from a proposal."""
    if is_duplicate_flag(proposal.key, existing_flags):
        logger.info(f"Skipping duplicate feature flag: {proposal.key}")
        return None

    try:
        flag = client.create_feature_flag(
            key=proposal.key,
            name=proposal.name,
            rollout_percentage=proposal.rollout_percentage,
        )
        logger.info(f"Created feature flag: {proposal.key} (ID: {flag.get('id')})")
        return flag
    except Exception as e:
        logger.error(f"Failed to create feature flag '{proposal.key}': {e}")
        return None


def _build_query_from_hint(query_type: str, query_hint: str) -> dict[str, Any]:
    """Build a basic PostHog query structure from the type and hint.

    This creates a minimal valid query that can be refined in the PostHog UI.
    The query_hint is stored in the description for reference.
    """
    if query_type == "funnels":
        return {
            "kind": "FunnelsQuery",
            "series": [],
            "funnelsFilter": {},
        }
    elif query_type == "retention":
        return {
            "kind": "RetentionQuery",
            "retentionFilter": {
                "retentionType": "retention_first_time",
                "totalIntervals": 11,
                "period": "Week",
            },
        }
    else:
        # Default to trends
        return {
            "kind": "TrendsQuery",
            "series": [],
            "trendsFilter": {},
        }
