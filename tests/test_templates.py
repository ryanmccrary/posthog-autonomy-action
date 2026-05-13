"""Tests for the comment template rendering."""

from __future__ import annotations

from src.commenter.templates import (
    render_dashboard_section,
    render_feature_flag_section,
    render_footer,
    render_header,
    render_insights_section,
    render_instrumentation_section,
)
from src.proposer.analytics import DashboardProposal, InsightProposal
from src.proposer.feature_flags import FeatureFlagProposal


class TestTemplates:
    def test_render_header(self) -> None:
        result = render_header("Added batch triggers", "medium")
        assert "Added batch triggers" in result
        assert "medium" in result
        assert "PostHog Product Autonomy Review" in result

    def test_render_instrumentation_with_commit(self) -> None:
        code_changes = {
            "missing_events": [
                {
                    "file_path": "src/app.ts",
                    "event_name": "trigger configured",
                    "rationale": "Track configuration",
                }
            ],
            "missing_properties": [],
            "missing_error_tracking": [
                {
                    "file_path": "src/api.ts",
                    "function_name": "fetchTrigger",
                }
            ],
            "missing_logging": [],
        }
        result = render_instrumentation_section("abc1234def", code_changes)
        assert "abc1234" in result
        assert "trigger configured" in result
        assert "fetchTrigger" in result
        assert "Revert the commit" in result

    def test_render_instrumentation_without_commit(self) -> None:
        code_changes = {
            "missing_events": [{"file_path": "a.ts", "event_name": "test", "rationale": ""}],
            "missing_properties": [],
            "missing_error_tracking": [],
            "missing_logging": [],
        }
        result = render_instrumentation_section(None, code_changes)
        assert "Suggested instrumentation" in result
        assert "could not push" in result

    def test_render_instrumentation_empty(self) -> None:
        code_changes = {
            "missing_events": [],
            "missing_properties": [],
            "missing_error_tracking": [],
            "missing_logging": [],
        }
        assert render_instrumentation_section("abc", code_changes) == ""

    def test_render_insights_section(self) -> None:
        proposals = [
            InsightProposal(
                name="Users per day",
                description="Daily active users",
                query_type="trends",
                query_hint="Event: $pageview",
                rationale="Track adoption",
            ),
            InsightProposal(
                name="Setup funnel",
                description="Config to activation",
                query_type="funnels",
                query_hint="Steps: config, activate",
                rationale="Track conversion",
            ),
        ]
        result = render_insights_section(proposals)
        assert "Proposed insights (2)" in result
        assert "Users per day" in result
        assert "Setup funnel" in result
        assert "react with 👍 to create" in result

    def test_render_insights_empty(self) -> None:
        assert render_insights_section([]) == ""

    def test_render_dashboard_section(self) -> None:
        proposal = DashboardProposal(
            name="Feature Dashboard",
            description="Tracks feature adoption",
        )
        result = render_dashboard_section(proposal)
        assert "Feature Dashboard" in result
        assert "react with 👍 to create" in result

    def test_render_dashboard_none(self) -> None:
        assert render_dashboard_section(None) == ""

    def test_render_feature_flag_section(self) -> None:
        proposal = FeatureFlagProposal(
            key="batch-triggers",
            name="Batch trigger rollout",
            rationale="Gradual rollout for safety",
            rollout_percentage=0,
        )
        result = render_feature_flag_section(proposal)
        assert "`batch-triggers`" in result
        assert "0%" in result
        assert "Gradual rollout" in result

    def test_render_feature_flag_none(self) -> None:
        assert render_feature_flag_section(None) == ""

    def test_render_footer(self) -> None:
        result = render_footer()
        assert "PostHog Product Autonomy Bot" in result
