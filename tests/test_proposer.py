"""Tests for the proposer modules."""

from __future__ import annotations

from src.proposer.analytics import (
    extract_dashboard_proposal,
    extract_insight_proposals,
)
from src.proposer.feature_flags import extract_feature_flag_proposal


class TestAnalyticsProposer:
    def test_extract_insight_proposals(self) -> None:
        analysis = {
            "proposed_insights": [
                {
                    "name": "Workflows by trigger type",
                    "description": "Breakdown of workflows by trigger type",
                    "query_type": "trends",
                    "query_hint": "Event: workflow_created, breakdown by trigger_type",
                    "rationale": "Track adoption of trigger types",
                },
                {
                    "name": "Batch trigger funnel",
                    "description": "Configuration to activation funnel",
                    "query_type": "funnels",
                    "query_hint": "Steps: configured, activated, ran",
                    "rationale": "Track conversion through setup flow",
                },
            ],
        }
        proposals = extract_insight_proposals(analysis)
        assert len(proposals) == 2
        assert proposals[0].name == "Workflows by trigger type"
        assert proposals[0].query_type == "trends"

    def test_extract_insight_proposals_with_prefix(self) -> None:
        analysis = {
            "proposed_insights": [
                {
                    "name": "Active users",
                    "description": "Count",
                    "query_type": "trends",
                    "query_hint": "",
                    "rationale": "",
                }
            ]
        }
        proposals = extract_insight_proposals(analysis, naming_prefix="[Auto] ")
        assert proposals[0].name == "[Auto] Active users"

    def test_extract_insight_proposals_preserves_existing_prefix(self) -> None:
        analysis = {
            "proposed_insights": [
                {
                    "name": "[Auto] Active users",
                    "description": "Count",
                    "query_type": "trends",
                    "query_hint": "",
                    "rationale": "",
                }
            ]
        }
        proposals = extract_insight_proposals(analysis, naming_prefix="[Auto] ")
        assert proposals[0].name == "[Auto] Active users"

    def test_extract_empty_proposals(self) -> None:
        assert extract_insight_proposals({"proposed_insights": []}) == []
        assert extract_insight_proposals({}) == []

    def test_extract_dashboard_proposal(self) -> None:
        analysis = {
            "proposed_dashboard": {
                "name": "Feature Dashboard",
                "description": "Tracks feature adoption",
                "include_insights": [0, 1],
            }
        }
        proposal = extract_dashboard_proposal(analysis)
        assert proposal is not None
        assert proposal.name == "Feature Dashboard"
        assert proposal.insight_indices == [0, 1]

    def test_extract_dashboard_proposal_none(self) -> None:
        assert extract_dashboard_proposal({"proposed_dashboard": None}) is None
        assert extract_dashboard_proposal({}) is None


class TestFeatureFlagProposer:
    def test_extract_feature_flag_proposal(self) -> None:
        analysis = {
            "proposed_feature_flag": {
                "key": "new-batch-triggers",
                "name": "Batch trigger rollout",
                "rationale": "New execution path needs gradual rollout",
                "rollout_percentage": 0,
            }
        }
        proposal = extract_feature_flag_proposal(analysis, flags_enabled=True)
        assert proposal is not None
        assert proposal.key == "new-batch-triggers"
        assert proposal.rollout_percentage == 0

    def test_extract_feature_flag_disabled(self) -> None:
        analysis = {
            "proposed_feature_flag": {
                "key": "some-flag",
                "name": "Some flag",
                "rationale": "Reason",
                "rollout_percentage": 0,
            }
        }
        # Feature flags disabled in config
        assert extract_feature_flag_proposal(analysis, flags_enabled=False) is None

    def test_extract_feature_flag_none(self) -> None:
        assert extract_feature_flag_proposal({"proposed_feature_flag": None}, flags_enabled=True) is None
