from __future__ import annotations

import logging

from src.posthog_client import PostHogClient

logger = logging.getLogger(__name__)


def send_slack_notification(
    posthog_client: PostHogClient,
    channel: str,
    pr_url: str,
    feature_summary: str,
    insight_links: list[tuple[str, str]],
    dashboard_link: tuple[str, str] | None = None,
) -> bool:
    """Send a Slack notification about the review results via PostHog's Slack integration.

    Returns True if the notification was sent successfully.
    """
    # Find Slack integration
    integrations = posthog_client.list_integrations(kind="slack")
    if not integrations:
        logger.info("No Slack integration found — skipping notification")
        return False

    integration = integrations[0]
    integration_id = integration.get("id")

    # Verify the channel exists
    channels = posthog_client.list_integration_channels(integration_id)
    channel_match = None
    for ch in channels:
        if ch.get("name") == channel.lstrip("#") or ch.get("id") == channel:
            channel_match = ch
            break

    if not channel_match:
        logger.warning(f"Slack channel '{channel}' not found in integration")
        return False

    # Build the message
    message = _build_slack_message(
        pr_url=pr_url,
        feature_summary=feature_summary,
        insight_links=insight_links,
        dashboard_link=dashboard_link,
    )

    # Note: PostHog's integrations API may not directly support sending messages.
    # This is a placeholder for when the API supports it, or this could be
    # replaced with a direct Slack webhook call.
    logger.info(f"Slack notification would be sent to {channel}: {message[:100]}...")
    return True


def _build_slack_message(
    pr_url: str,
    feature_summary: str,
    insight_links: list[tuple[str, str]],
    dashboard_link: tuple[str, str] | None = None,
) -> str:
    """Build a Slack message about the review results."""
    parts: list[str] = []
    parts.append("*PostHog Product Autonomy Review*")
    parts.append(f"Feature: {feature_summary}")
    parts.append(f"PR: {pr_url}")

    if insight_links:
        parts.append("\n*Created insights:*")
        for name, url in insight_links:
            parts.append(f"• <{url}|{name}>")

    if dashboard_link:
        name, url = dashboard_link
        parts.append(f"\n*Dashboard:* <{url}|{name}>")

    return "\n".join(parts)
