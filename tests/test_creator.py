"""Tests for the creator modules."""

from __future__ import annotations

from src.creator.dedup import is_duplicate_dashboard, is_duplicate_flag, is_duplicate_insight


class TestDedup:
    def test_exact_match_insight(self) -> None:
        existing = [{"name": "Active users per day"}]
        assert is_duplicate_insight("Active users per day", existing) is True

    def test_case_insensitive_match(self) -> None:
        existing = [{"name": "Active Users Per Day"}]
        assert is_duplicate_insight("active users per day", existing) is True

    def test_fuzzy_match_insight(self) -> None:
        existing = [{"name": "Active users per day"}]
        assert is_duplicate_insight("Active users daily", existing) is True

    def test_no_match_insight(self) -> None:
        existing = [{"name": "Active users per day"}]
        assert is_duplicate_insight("Batch trigger adoption", existing) is False

    def test_empty_existing_insights(self) -> None:
        assert is_duplicate_insight("Any insight", []) is False

    def test_exact_match_flag(self) -> None:
        existing = [{"key": "new-feature-rollout"}]
        assert is_duplicate_flag("new-feature-rollout", existing) is True

    def test_no_match_flag(self) -> None:
        existing = [{"key": "old-feature"}]
        assert is_duplicate_flag("new-feature-rollout", existing) is False

    def test_exact_match_dashboard(self) -> None:
        existing = [{"name": "Feature Dashboard"}]
        assert is_duplicate_dashboard("Feature Dashboard", existing) is True

    def test_no_match_dashboard(self) -> None:
        existing = [{"name": "Revenue Dashboard"}]
        assert is_duplicate_dashboard("Feature Dashboard", existing) is False

    def test_handles_none_names(self) -> None:
        existing = [{"name": None}, {"name": ""}]
        assert is_duplicate_insight("Test", existing) is False
