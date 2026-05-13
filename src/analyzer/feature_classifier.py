from __future__ import annotations

from enum import Enum

from src.github_client import PRData


class FeatureSize(str, Enum):
    TRIVIAL = "trivial"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# File extensions that count as source code
SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
}

# Patterns that indicate non-source files
SKIP_PATTERNS = {
    "docs/",
    "doc/",
    ".md",
    ".rst",
    ".test.",
    ".spec.",
    "__test__",
    "_test.",
    ".github/",
    ".circleci/",
    "__snapshots__/",
    "generated/",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".env",
    ".gitignore",
    ".editorconfig",
}


def classify_feature_size(pr_data: PRData) -> FeatureSize:
    """Classify the size of the feature based on the PR diff."""
    source_additions = 0
    source_files_changed = 0

    for f in pr_data.files:
        if _is_source_file(f.filename):
            source_additions += f.additions
            source_files_changed += 1

    if source_additions < 10:
        return FeatureSize.TRIVIAL
    if source_additions < 50 and source_files_changed <= 3:
        return FeatureSize.SMALL
    if source_additions < 200 or source_files_changed <= 8:
        return FeatureSize.MEDIUM
    return FeatureSize.LARGE


def count_source_lines(pr_data: PRData) -> int:
    """Count the number of source code lines added/modified in the PR."""
    total = 0
    for f in pr_data.files:
        if _is_source_file(f.filename):
            total += f.additions + f.deletions
    return total


def _is_source_file(filename: str) -> bool:
    """Check if a file is a source code file (not docs, tests, config, etc.)."""
    lower = filename.lower()
    for pattern in SKIP_PATTERNS:
        if pattern in lower:
            return False
    return any(lower.endswith(ext) for ext in SOURCE_EXTENSIONS)
