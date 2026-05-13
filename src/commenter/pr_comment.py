from __future__ import annotations

import logging
from typing import Any

from src.commenter.templates import (
    render_dashboard_section,
    render_feature_flag_section,
    render_footer,
    render_header,
    render_insights_section,
    render_instrumentation_section,
)
from src.github_client import GitHubClient
from src.proposer.analytics import DashboardProposal, InsightProposal
from src.proposer.feature_flags import FeatureFlagProposal

logger = logging.getLogger(__name__)


def post_review_comment(
    github_client: GitHubClient,
    pr_number: int,
    feature_summary: str,
    feature_size: str,
    commit_sha: str | None,
    code_changes: dict[str, Any],
    insight_proposals: list[InsightProposal],
    dashboard_proposal: DashboardProposal | None,
    flag_proposal: FeatureFlagProposal | None,
) -> int | None:
    """Post or update the review comment on the PR. Returns the comment ID."""
    body = _build_comment_body(
        feature_summary=feature_summary,
        feature_size=feature_size,
        commit_sha=commit_sha,
        code_changes=code_changes,
        insight_proposals=insight_proposals,
        dashboard_proposal=dashboard_proposal,
        flag_proposal=flag_proposal,
    )

    # Check if we have anything meaningful to say
    has_code_changes = any(
        code_changes.get(key)
        for key in ("missing_events", "missing_properties", "missing_error_tracking", "missing_logging")
    )
    has_proposals = bool(insight_proposals) or dashboard_proposal is not None or flag_proposal is not None

    if not has_code_changes and not has_proposals:
        logger.info("No changes or proposals to comment about — skipping comment")
        return None

    # Check for existing bot comment
    existing_comment_id = github_client.find_bot_comment(pr_number)

    if existing_comment_id:
        logger.info(f"Updating existing comment {existing_comment_id}")
        github_client.update_comment(existing_comment_id, body)
        return existing_comment_id
    else:
        logger.info("Posting new review comment")
        return github_client.post_comment(pr_number, body)


def _build_comment_body(
    feature_summary: str,
    feature_size: str,
    commit_sha: str | None,
    code_changes: dict[str, Any],
    insight_proposals: list[InsightProposal],
    dashboard_proposal: DashboardProposal | None,
    flag_proposal: FeatureFlagProposal | None,
) -> str:
    """Build the full markdown comment body."""
    sections: list[str] = []

    sections.append(render_header(feature_summary, feature_size))

    instrumentation = render_instrumentation_section(commit_sha, code_changes)
    if instrumentation:
        sections.append(instrumentation)

    insights = render_insights_section(insight_proposals)
    if insights:
        sections.append(insights)

    dashboard = render_dashboard_section(dashboard_proposal)
    if dashboard:
        sections.append(dashboard)

    flag = render_feature_flag_section(flag_proposal)
    if flag:
        sections.append(flag)

    sections.append(render_footer())

    return "\n\n".join(sections)
