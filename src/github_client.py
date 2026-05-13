from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BOT_AUTHOR_EMAIL = "bot@posthog.com"
BOT_AUTHOR_NAME = "PostHog Autonomy Bot"
BOT_COMMENT_MARKER = "<!-- posthog-product-autonomy-review -->"
SKIP_MARKER = "[skip-autonomy]"


@dataclass
class PRFile:
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    patch: str = ""


@dataclass
class PRData:
    number: int
    title: str
    body: str
    author: str
    base_ref: str
    head_ref: str
    head_sha: str
    labels: list[str] = field(default_factory=list)
    files: list[PRFile] = field(default_factory=list)
    is_draft: bool = False
    is_fork: bool = False


class GitHubClient:
    def __init__(self, token: str, repository: str) -> None:
        self._token = token
        self._repository = repository
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def fetch_pr(self, pr_number: int) -> PRData:
        """Fetch PR metadata and file list."""
        pr_resp = self._client.get(f"/repos/{self._repository}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        pr = pr_resp.json()

        files_resp = self._client.get(
            f"/repos/{self._repository}/pulls/{pr_number}/files",
            params={"per_page": 300},
        )
        files_resp.raise_for_status()

        files = [
            PRFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch", ""),
            )
            for f in files_resp.json()
        ]

        head = pr.get("head", {})
        base = pr.get("base", {})

        return PRData(
            number=pr_number,
            title=pr.get("title", ""),
            body=pr.get("body", "") or "",
            author=pr.get("user", {}).get("login", ""),
            base_ref=base.get("ref", "main"),
            head_ref=head.get("ref", ""),
            head_sha=head.get("sha", ""),
            labels=[label.get("name", "") for label in pr.get("labels", [])],
            files=files,
            is_draft=pr.get("draft", False),
            is_fork=head.get("repo", {}).get("full_name", "") != self._repository,
        )

    def fetch_file_content(self, path: str, ref: str) -> str | None:
        """Fetch a file's content at a specific ref."""
        resp = self._client.get(
            f"/repos/{self._repository}/contents/{path}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.v3.raw"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text

    def post_comment(self, pr_number: int, body: str) -> int:
        """Post a comment on a PR. Returns the comment ID."""
        resp = self._client.post(
            f"/repos/{self._repository}/issues/{pr_number}/comments",
            json={"body": f"{BOT_COMMENT_MARKER}\n{body}"},
        )
        resp.raise_for_status()
        return int(resp.json()["id"])

    def update_comment(self, comment_id: int, body: str) -> None:
        """Update an existing comment."""
        resp = self._client.patch(
            f"/repos/{self._repository}/issues/comments/{comment_id}",
            json={"body": f"{BOT_COMMENT_MARKER}\n{body}"},
        )
        resp.raise_for_status()

    def find_bot_comment(self, pr_number: int) -> int | None:
        """Find the bot's existing comment on a PR."""
        resp = self._client.get(
            f"/repos/{self._repository}/issues/{pr_number}/comments",
            params={"per_page": 100},
        )
        resp.raise_for_status()

        for comment in resp.json():
            if BOT_COMMENT_MARKER in (comment.get("body", "") or ""):
                return int(comment["id"])
        return None

    def get_comment_reactions(self, comment_id: int) -> dict[str, int]:
        """Get reaction counts on a comment."""
        resp = self._client.get(
            f"/repos/{self._repository}/issues/comments/{comment_id}/reactions",
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()

        counts: dict[str, int] = {}
        for reaction in resp.json():
            content = reaction.get("content", "")
            counts[content] = counts.get(content, 0) + 1
        return counts

    def get_latest_commit_author(self, pr_number: int) -> str:
        """Get the author email of the latest commit on a PR."""
        resp = self._client.get(
            f"/repos/{self._repository}/pulls/{pr_number}/commits",
            params={"per_page": 1},
        )
        resp.raise_for_status()
        commits = resp.json()
        if not commits:
            return ""
        return commits[-1].get("commit", {}).get("author", {}).get("email", "")

    def close(self) -> None:
        self._client.close()


def should_skip_bot_commit(pr_data: PRData) -> bool:
    """Check if the latest commit was made by the bot (to prevent infinite loops)."""
    # Check commit message for skip marker
    # This is checked at the workflow level too, but belt-and-suspenders
    return False  # Actual check done via get_latest_commit_author


def commit_and_push(
    repo_path: Path,
    files: list[str],
    message: str,
    branch: str,
) -> str | None:
    """Stage files, commit, and push to the PR branch. Returns the commit SHA or None on failure."""
    try:
        # Configure git author
        _run_git(repo_path, ["config", "user.email", BOT_AUTHOR_EMAIL])
        _run_git(repo_path, ["config", "user.name", BOT_AUTHOR_NAME])

        # Stage files
        for file_path in files:
            _run_git(repo_path, ["add", file_path])

        # Check if there are staged changes
        result = _run_git(repo_path, ["diff", "--cached", "--name-only"])
        if not result.strip():
            logger.info("No changes to commit")
            return None

        # Commit
        full_message = f"{message}\n\n{SKIP_MARKER}"
        _run_git(repo_path, ["commit", "-m", full_message])

        # Push
        _run_git(repo_path, ["push", "origin", f"HEAD:{branch}"])

        # Get the commit SHA
        sha = _run_git(repo_path, ["rev-parse", "HEAD"]).strip()
        logger.info(f"Pushed commit {sha} to {branch}")
        return sha

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr}")
        return None


def _run_git(repo_path: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
