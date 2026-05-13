from __future__ import annotations

from typing import Any

from src.proposer.analytics import DashboardProposal, InsightProposal
from src.proposer.feature_flags import FeatureFlagProposal


def render_header(feature_summary: str, feature_size: str) -> str:
    """Render the comment header."""
    return f"""## PostHog Product Autonomy Review

### Feature detected
**{feature_summary}** ({feature_size} feature)

---"""


def render_instrumentation_section(
    commit_sha: str | None,
    code_changes: dict[str, Any],
) -> str:
    """Render the section about code changes that were committed."""
    parts: list[str] = []

    missing_events = code_changes.get("missing_events", [])
    missing_properties = code_changes.get("missing_properties", [])
    missing_error_tracking = code_changes.get("missing_error_tracking", [])
    missing_logging = code_changes.get("missing_logging", [])

    total_changes = len(missing_events) + len(missing_properties) + len(missing_error_tracking) + len(missing_logging)

    if total_changes == 0:
        return ""

    if commit_sha:
        parts.append(f"### Instrumentation added (commit {commit_sha[:7]})")
        parts.append("")
        parts.append("The following instrumentation was added to this PR:")
    else:
        parts.append("### Suggested instrumentation")
        parts.append("")
        parts.append("The following instrumentation changes are suggested (could not push to branch):")

    if missing_events:
        parts.append("")
        parts.append("**Analytics events:**")
        for event in missing_events:
            parts.append(f"- `{event.get('file_path', '')}` — Added `{event.get('event_name', '')}` event")
            if event.get("rationale"):
                parts.append(f"  > {event['rationale']}")

    if missing_properties:
        parts.append("")
        parts.append("**Event properties:**")
        for prop in missing_properties:
            parts.append(
                f"- `{prop.get('file_path', '')}` — Added `{prop.get('property_name', '')}` "
                f"property to `{prop.get('existing_event', '')}` event"
            )
            if prop.get("rationale"):
                parts.append(f"  > {prop['rationale']}")

    if missing_error_tracking:
        parts.append("")
        parts.append("**Error tracking:**")
        for item in missing_error_tracking:
            parts.append(
                f"- `{item.get('file_path', '')}` — Wrapped `{item.get('function_name', '')}` with error capture"
            )

    if missing_logging:
        parts.append("")
        parts.append("**Logging:**")
        for item in missing_logging:
            parts.append(
                f"- `{item.get('file_path', '')}` — Added structured logging for `{item.get('function_name', '')}`"
            )

    if commit_sha:
        parts.append("")
        parts.append(
            "> Review the commit to verify these changes match your conventions. "
            "Revert the commit if any changes are unwanted."
        )

    return "\n".join(parts)


def render_insights_section(proposals: list[InsightProposal]) -> str:
    """Render the proposed insights section."""
    if not proposals:
        return ""

    lines: list[str] = []
    lines.append("\n<details>")
    lines.append(f"<summary>Proposed insights ({len(proposals)}) — react with 👍 to create</summary>")
    lines.append("")

    for i, p in enumerate(proposals, 1):
        lines.append(f"{i}. **{p.name}** — {p.description}")
        lines.append(f"   - Type: {p.query_type}")
        lines.append(f"   - Query: {p.query_hint}")
        if p.rationale:
            lines.append(f"   - Why: {p.rationale}")

    lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def render_dashboard_section(proposal: DashboardProposal | None) -> str:
    """Render the proposed dashboard section."""
    if not proposal:
        return ""

    lines: list[str] = []
    lines.append("\n<details>")
    lines.append("<summary>Proposed dashboard — react with 👍 to create</summary>")
    lines.append("")
    lines.append(f"**{proposal.name}** — {proposal.description}")
    lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def render_feature_flag_section(proposal: FeatureFlagProposal | None) -> str:
    """Render the proposed feature flag section."""
    if not proposal:
        return ""

    lines: list[str] = []
    lines.append("\n<details>")
    lines.append("<summary>Feature flag suggestion — react with 👍 to create</summary>")
    lines.append("")
    lines.append(f"**`{proposal.key}`** — {proposal.name}")
    lines.append(f"Starting at {proposal.rollout_percentage}% rollout.")
    if proposal.rationale:
        lines.append(f"\n{proposal.rationale}")
    lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def render_footer() -> str:
    """Render the comment footer."""
    return """
---
*React with 👍 on a section to approve resource creation. React with 🔔 for Slack notifications.*

<sub>PostHog Product Autonomy Bot</sub>"""


def render_created_resources(
    insight_links: list[tuple[str, str]],
    dashboard_link: tuple[str, str] | None,
    flag_link: tuple[str, str] | None,
) -> str:
    """Render a section showing links to created resources."""
    parts: list[str] = []
    parts.append("\n### Created resources")

    if insight_links:
        parts.append("\n**Insights:**")
        for name, url in insight_links:
            parts.append(f"- [{name}]({url})")

    if dashboard_link:
        name, url = dashboard_link
        parts.append(f"\n**Dashboard:** [{name}]({url})")

    if flag_link:
        name, url = flag_link
        parts.append(f"\n**Feature flag:** [{name}]({url})")

    return "\n".join(parts)
