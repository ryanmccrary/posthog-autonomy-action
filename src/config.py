from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EventNamingConfig:
    style: str = "snake_case"
    prefix: str = ""


@dataclass
class InsightNamingConfig:
    prefix: str = ""


@dataclass
class FeatureFlagConfig:
    enabled: bool = False
    require_approval: bool = True


@dataclass
class SlackConfig:
    enabled: bool = False
    default_channel: str = ""


@dataclass
class Config:
    # Required inputs
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    posthog_project_id: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""

    # Repo-level config
    products: list[str] = field(default_factory=list)
    min_lines: int = 10
    skip_paths: list[str] = field(
        default_factory=lambda: [
            "docs/**",
            "**/*.test.*",
            "**/*.spec.*",
            "**/__snapshots__/**",
            ".github/**",
            "**/generated/**",
        ]
    )
    event_naming: EventNamingConfig = field(default_factory=EventNamingConfig)
    insight_naming: InsightNamingConfig = field(default_factory=InsightNamingConfig)
    feature_flags: FeatureFlagConfig = field(default_factory=FeatureFlagConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    slack_channel: str = ""

    # GitHub context
    github_repository: str = ""
    github_event_name: str = ""
    pr_number: int = 0


def load_config() -> Config:
    """Load configuration from environment variables and optional repo config file."""
    config = Config(
        posthog_api_key=os.environ.get("POSTHOG_API_KEY", ""),
        posthog_host=os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com"),
        posthog_project_id=os.environ.get("POSTHOG_PROJECT_ID", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        github_token=os.environ.get("GITHUB_TOKEN", ""),
        github_repository=os.environ.get("GITHUB_REPOSITORY", ""),
        github_event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
        slack_channel=os.environ.get("SLACK_CHANNEL", ""),
    )

    # Parse products from env
    products_env = os.environ.get("PRODUCTS", "")
    if products_env:
        config.products = [p.strip() for p in products_env.split(",") if p.strip()]

    # Load repo-level config if it exists
    config_path = Path(os.environ.get("CONFIG_PATH", ".posthog/autonomy.yml"))
    if config_path.exists():
        _merge_repo_config(config, config_path)

    # Parse PR number from GitHub event
    pr_number = os.environ.get("PR_NUMBER", "")
    if pr_number:
        config.pr_number = int(pr_number)
    else:
        config.pr_number = _parse_pr_number_from_event()

    return config


def _merge_repo_config(config: Config, config_path: Path) -> None:
    """Merge repo-level YAML config into the Config object."""
    with open(config_path) as f:
        repo_config: dict[str, Any] = yaml.safe_load(f) or {}

    if "products" in repo_config and not config.products:
        config.products = repo_config["products"]

    if "min_lines" in repo_config:
        config.min_lines = repo_config["min_lines"]

    if "skip_paths" in repo_config:
        config.skip_paths = repo_config["skip_paths"]

    if "event_naming" in repo_config:
        en = repo_config["event_naming"]
        config.event_naming = EventNamingConfig(
            style=en.get("style", "snake_case"),
            prefix=en.get("prefix", ""),
        )

    if "insight_naming" in repo_config:
        config.insight_naming = InsightNamingConfig(
            prefix=repo_config["insight_naming"].get("prefix", ""),
        )

    if "feature_flags" in repo_config:
        ff = repo_config["feature_flags"]
        config.feature_flags = FeatureFlagConfig(
            enabled=ff.get("enabled", False),
            require_approval=ff.get("require_approval", True),
        )

    if "slack" in repo_config:
        sl = repo_config["slack"]
        config.slack = SlackConfig(
            enabled=sl.get("enabled", False),
            default_channel=sl.get("default_channel", ""),
        )


def _parse_pr_number_from_event() -> int:
    """Parse the PR number from the GitHub event JSON."""
    import json

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not Path(event_path).exists():
        return 0

    with open(event_path) as f:
        event = json.load(f)

    pr = event.get("pull_request", {})
    return int(pr.get("number", 0))
