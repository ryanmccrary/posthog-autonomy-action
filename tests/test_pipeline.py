"""Tests for the main pipeline triage logic."""

from __future__ import annotations

from src.config import Config
from src.github_client import PRData, PRFile
from src.main import should_skip_pr


class TestTriage:
    def _make_config(self, **kwargs) -> Config:  # type: ignore[no-untyped-def]
        defaults = {"min_lines": 10}
        defaults.update(kwargs)
        return Config(**defaults)

    def _make_pr(self, **kwargs) -> PRData:  # type: ignore[no-untyped-def]
        defaults = {
            "number": 1,
            "title": "Add feature",
            "body": "",
            "author": "developer",
            "base_ref": "main",
            "head_ref": "feature-branch",
            "head_sha": "abc123",
            "files": [
                PRFile(filename="src/app.ts", status="modified", additions=50, deletions=10),
            ],
        }
        defaults.update(kwargs)
        return PRData(**defaults)

    def test_skip_draft_pr(self) -> None:
        pr = self._make_pr(is_draft=True)
        assert should_skip_pr(pr, self._make_config()) == "PR is a draft"

    def test_skip_dependabot(self) -> None:
        pr = self._make_pr(author="dependabot[bot]")
        assert should_skip_pr(pr, self._make_config()) is not None
        assert "dependency bot" in should_skip_pr(pr, self._make_config())  # type: ignore

    def test_skip_renovate(self) -> None:
        pr = self._make_pr(author="renovate[bot]")
        assert should_skip_pr(pr, self._make_config()) is not None

    def test_skip_too_few_lines(self) -> None:
        pr = self._make_pr(files=[PRFile(filename="src/app.ts", status="modified", additions=3, deletions=1)])
        assert should_skip_pr(pr, self._make_config(min_lines=10)) is not None
        assert "Too few" in should_skip_pr(pr, self._make_config(min_lines=10))  # type: ignore

    def test_skip_docs_only(self) -> None:
        pr = self._make_pr(
            files=[
                PRFile(filename="docs/guide.md", status="modified", additions=100, deletions=0),
                PRFile(filename="docs/api.md", status="added", additions=50, deletions=0),
            ]
        )
        result = should_skip_pr(pr, self._make_config(min_lines=5))
        # These match skip patterns
        assert result is not None

    def test_skip_all_config_files(self) -> None:
        pr = self._make_pr(
            files=[
                PRFile(filename=".github/workflows/ci.yml", status="modified", additions=20, deletions=5),
            ]
        )
        result = should_skip_pr(pr, self._make_config(min_lines=5))
        assert result is not None

    def test_no_skip_normal_pr(self) -> None:
        pr = self._make_pr()
        assert should_skip_pr(pr, self._make_config()) is None

    def test_no_skip_mixed_files(self) -> None:
        pr = self._make_pr(
            files=[
                PRFile(filename="docs/guide.md", status="modified", additions=50, deletions=0),
                PRFile(filename="src/feature.ts", status="added", additions=100, deletions=0),
            ]
        )
        assert should_skip_pr(pr, self._make_config()) is None
