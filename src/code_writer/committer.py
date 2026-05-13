from __future__ import annotations

import logging
from pathlib import Path

from src.github_client import commit_and_push

logger = logging.getLogger(__name__)


def commit_instrumentation_changes(
    repo_root: Path,
    modified_files: list[str],
    feature_summary: str,
    branch: str,
) -> str | None:
    """Commit and push instrumentation changes. Returns the commit SHA or None."""
    if not modified_files:
        logger.info("No modified files to commit")
        return None

    # Build a descriptive commit message
    message = f"chore: add PostHog instrumentation for {feature_summary}"

    logger.info(f"Committing {len(modified_files)} files: {', '.join(modified_files)}")

    sha = commit_and_push(
        repo_path=repo_root,
        files=modified_files,
        message=message,
        branch=branch,
    )

    if sha:
        logger.info(f"Successfully pushed instrumentation commit: {sha}")
    else:
        logger.warning("Failed to push instrumentation commit")

    return sha
