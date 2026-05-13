"""PostHog Product Autonomy Action — main entry point.

Orchestrates the pipeline:
1. Triage — skip trivial PRs
2. Context gathering — fetch PR data, surrounding code, PostHog project state
3. Semantic analysis — LLM-based analysis of instrumentation gaps
4. Code changes — push instrumentation fixes to the PR branch
5. Proposal comment — post insights/dashboard/flag proposals
"""

from __future__ import annotations

import fnmatch
import logging
import os
import sys
from pathlib import Path
from typing import Any

from src.analyzer.feature_classifier import FeatureSize, classify_feature_size, count_source_lines
from src.analyzer.instrumentation import (
    ExistingInstrumentation,
    merge_instrumentation,
    scan_file_for_instrumentation,
)
from src.analyzer.pr_analyzer import analyze_pr
from src.analyzer.product_detector import detect_products_from_files
from src.code_writer.committer import commit_instrumentation_changes
from src.code_writer.writer import apply_edits_to_files, apply_instrumentation_changes
from src.commenter.pr_comment import post_review_comment
from src.config import Config, load_config
from src.github_client import BOT_AUTHOR_EMAIL, GitHubClient, PRData
from src.proposer.analytics import extract_dashboard_proposal, extract_insight_proposals
from src.proposer.feature_flags import extract_feature_flag_proposal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    config = load_config()

    if not config.posthog_api_key:
        logger.error("POSTHOG_API_KEY is required")
        sys.exit(1)
    if not config.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY is required")
        sys.exit(1)
    if not config.posthog_project_id:
        logger.error("POSTHOG_PROJECT_ID is required")
        sys.exit(1)
    if not config.github_token:
        logger.error("GITHUB_TOKEN is required")
        sys.exit(1)
    if not config.github_repository:
        logger.error("GITHUB_REPOSITORY is required")
        sys.exit(1)
    if not config.pr_number:
        logger.error("Could not determine PR number from event")
        sys.exit(1)

    github_client = GitHubClient(config.github_token, config.github_repository)

    try:
        run_pipeline(config, github_client)
    finally:
        github_client.close()


def run_pipeline(config: Config, github_client: GitHubClient) -> None:
    """Run the full review pipeline."""

    # --- Phase 1: Fetch PR data ---
    logger.info(f"Fetching PR #{config.pr_number} from {config.github_repository}")
    pr_data = github_client.fetch_pr(config.pr_number)

    # --- Phase 1b: Triage ---
    skip_reason = should_skip_pr(pr_data, config)
    if skip_reason:
        logger.info(f"Skipping PR: {skip_reason}")
        return

    # Check if the latest commit is from the bot (infinite loop prevention)
    latest_author = github_client.get_latest_commit_author(config.pr_number)
    if latest_author == BOT_AUTHOR_EMAIL:
        logger.info("Latest commit is from the bot — skipping to prevent infinite loop")
        return

    # --- Phase 2: Context gathering ---
    logger.info("Gathering context...")

    # Classify feature size
    feature_size = classify_feature_size(pr_data)
    logger.info(f"Feature size: {feature_size.value}")

    if feature_size == FeatureSize.TRIVIAL:
        logger.info("Trivial feature — skipping analysis")
        return

    # Fetch surrounding code context and scan for existing instrumentation
    surrounding_context, file_contents = gather_code_context(github_client, pr_data)
    existing_instrumentation = scan_for_instrumentation(file_contents)

    # Detect which PostHog products are in use
    products = detect_products_from_files(file_contents, config.products or None)
    if not products:
        logger.info("No PostHog products detected in the codebase — skipping")
        return
    logger.info(f"Products detected: {', '.join(p.value for p in products)}")

    # Fetch PostHog project context
    posthog_context = fetch_posthog_context(config)

    # --- Phase 3: Semantic analysis ---
    logger.info("Running LLM analysis...")
    analysis = analyze_pr(
        config=config,
        pr_data=pr_data,
        feature_size=feature_size,
        existing_instrumentation=existing_instrumentation,
        products=products,
        event_definitions=posthog_context["event_definitions"],
        property_definitions=posthog_context["property_definitions"],
        insight_names=posthog_context["insight_names"],
        surrounding_context=surrounding_context,
    )
    logger.info(f"Analysis complete: {analysis.get('feature_summary', 'unknown')}")

    # --- Phase 4: Code changes ---
    commit_sha = None
    code_changes = analysis.get("code_changes", {})
    has_code_changes = any(
        code_changes.get(key)
        for key in ("missing_events", "missing_properties", "missing_error_tracking", "missing_logging")
    )

    if has_code_changes and not pr_data.is_fork:
        logger.info("Applying instrumentation changes...")
        repo_root = Path(os.environ.get("GITHUB_WORKSPACE", "."))

        edits = apply_instrumentation_changes(
            anthropic_api_key=config.anthropic_api_key,
            analysis=analysis,
            file_contents=file_contents,
            repo_root=repo_root,
        )

        if edits:
            modified_files = apply_edits_to_files(edits, repo_root)

            if modified_files:
                commit_sha = commit_instrumentation_changes(
                    repo_root=repo_root,
                    modified_files=modified_files,
                    feature_summary=analysis.get("feature_summary", "unknown feature"),
                    branch=pr_data.head_ref,
                )
    elif pr_data.is_fork:
        logger.info("PR is from a fork — cannot push commits, will suggest in comment only")

    # --- Phase 5: Proposal comment ---
    logger.info("Posting review comment...")
    insight_proposals = extract_insight_proposals(
        analysis,
        naming_prefix=config.insight_naming.prefix,
    )
    dashboard_proposal = extract_dashboard_proposal(
        analysis,
        naming_prefix=config.insight_naming.prefix,
    )
    flag_proposal = extract_feature_flag_proposal(
        analysis,
        flags_enabled=config.feature_flags.enabled,
    )

    comment_id = post_review_comment(
        github_client=github_client,
        pr_number=config.pr_number,
        feature_summary=analysis.get("feature_summary", "Unknown feature"),
        feature_size=analysis.get("feature_size", feature_size.value),
        commit_sha=commit_sha,
        code_changes=code_changes,
        insight_proposals=insight_proposals,
        dashboard_proposal=dashboard_proposal,
        flag_proposal=flag_proposal,
    )

    if comment_id:
        logger.info(f"Review comment posted (ID: {comment_id})")
    else:
        logger.info("No review comment needed")

    logger.info("Pipeline complete")


def should_skip_pr(pr_data: PRData, config: Config) -> str | None:
    """Check if the PR should be skipped. Returns the reason or None."""
    if pr_data.is_draft:
        return "PR is a draft"

    # Check for bot/dependency update PRs
    bot_authors = {"dependabot[bot]", "renovate[bot]", "dependabot", "renovate"}
    if pr_data.author in bot_authors:
        return f"PR by dependency bot: {pr_data.author}"

    # Check minimum lines
    source_lines = count_source_lines(pr_data)
    if source_lines < config.min_lines:
        return f"Too few source code changes ({source_lines} < {config.min_lines})"

    # Check if all files match skip patterns
    non_skipped_files = []
    for f in pr_data.files:
        should_skip = False
        for pattern in config.skip_paths:
            if fnmatch.fnmatch(f.filename, pattern):
                should_skip = True
                break
        if not should_skip:
            non_skipped_files.append(f)

    if not non_skipped_files:
        return "All changed files match skip patterns"

    return None


def gather_code_context(
    github_client: GitHubClient,
    pr_data: PRData,
) -> tuple[dict[str, str], dict[str, str]]:
    """Gather surrounding code context for the PR.

    Returns:
        surrounding_context: dict of file path -> content for related files
        file_contents: dict of file path -> content for changed files + surrounding files
    """
    surrounding_context: dict[str, str] = {}
    file_contents: dict[str, str] = {}

    for pr_file in pr_data.files:
        if pr_file.status == "removed":
            continue

        # Fetch the full file content
        content = github_client.fetch_file_content(pr_file.filename, pr_data.head_ref)
        if content:
            file_contents[pr_file.filename] = content

        # Also fetch nearby files in the same directory to understand patterns
        dir_path = str(Path(pr_file.filename).parent)
        if dir_path and dir_path != ".":
            # Try to find sibling files that might have instrumentation
            for sibling_suffix in ["index.ts", "index.tsx", "index.py", "__init__.py", "api.py", "views.py"]:
                sibling_path = f"{dir_path}/{sibling_suffix}"
                if sibling_path not in file_contents and sibling_path not in surrounding_context:
                    sibling_content = github_client.fetch_file_content(sibling_path, pr_data.head_ref)
                    if sibling_content:
                        surrounding_context[sibling_path] = sibling_content
                        file_contents[sibling_path] = sibling_content

    return surrounding_context, file_contents


def scan_for_instrumentation(file_contents: dict[str, str]) -> ExistingInstrumentation:
    """Scan all gathered files for existing instrumentation."""
    scans = []
    for path, content in file_contents.items():
        scans.append(scan_file_for_instrumentation(path, content))
    return merge_instrumentation(scans)


def fetch_posthog_context(config: Config) -> dict[str, Any]:
    """Fetch project context from PostHog API."""
    from src.posthog_client import PostHogClient

    client = PostHogClient(config.posthog_api_key, config.posthog_host, config.posthog_project_id)

    context: dict[str, Any] = {
        "event_definitions": [],
        "property_definitions": [],
        "insight_names": [],
        "existing_flags": [],
        "existing_insights": [],
        "existing_dashboards": [],
    }

    try:
        context["event_definitions"] = client.list_event_definitions()
        logger.info(f"Fetched {len(context['event_definitions'])} event definitions")
    except Exception as e:
        logger.warning(f"Failed to fetch event definitions: {e}")

    try:
        context["property_definitions"] = client.list_property_definitions()
        logger.info(f"Fetched {len(context['property_definitions'])} property definitions")
    except Exception as e:
        logger.warning(f"Failed to fetch property definitions: {e}")

    try:
        insights = client.list_insights()
        context["existing_insights"] = insights
        context["insight_names"] = [i.get("name", "") for i in insights if i.get("name")]
        logger.info(f"Fetched {len(insights)} existing insights")
    except Exception as e:
        logger.warning(f"Failed to fetch insights: {e}")

    try:
        context["existing_flags"] = client.list_feature_flags()
        logger.info(f"Fetched {len(context['existing_flags'])} existing feature flags")
    except Exception as e:
        logger.warning(f"Failed to fetch feature flags: {e}")

    try:
        context["existing_dashboards"] = client.list_dashboards()
        logger.info(f"Fetched {len(context['existing_dashboards'])} existing dashboards")
    except Exception as e:
        logger.warning(f"Failed to fetch dashboards: {e}")

    client.close()
    return context


if __name__ == "__main__":
    main()
