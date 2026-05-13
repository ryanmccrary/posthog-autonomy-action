from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from src.analyzer.feature_classifier import FeatureSize
from src.analyzer.instrumentation import ExistingInstrumentation, summarize_instrumentation
from src.analyzer.product_detector import PostHogProduct
from src.config import Config
from src.github_client import PRData

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
You are a PostHog instrumentation reviewer. Your job is to analyze a pull request, \
understand what features are being added or changed, and identify missing PostHog \
instrumentation.

You will receive:
1. The PR diff (file changes with content)
2. Surrounding code context (existing instrumentation in nearby files)
3. The customer's existing event definitions and property schemas
4. The customer's existing insights (for naming conventions)
5. Which PostHog products the customer uses

Your task:
1. Understand what this PR adds or changes at a product/feature level
2. Check for missing analytics events, properties, error tracking, and logging
3. Propose PostHog insights and dashboards that would help track this feature
4. Only suggest a feature flag if the change warrants gradual rollout

Rules:
- Be concise. Focus on the most impactful gaps, not every possible event.
- Match the customer's existing naming conventions for events and properties.
- For trivial features: do not suggest any insights or code changes.
- For small features (< 50 lines): suggest at most 2-3 insights, no dashboard.
- For medium features: suggest at most 3-5 insights, optionally a dashboard.
- For large features: suggest up to 5 insights + a dashboard.
- Only suggest feature flags for: new UI implementations, risky behavioral changes, \
  or features that change data processing. NOT for every small addition.
- When suggesting missing properties on existing events, explain WHY the property \
  is needed (what question it answers that currently can't be answered).
- Check BOTH the PR diff AND surrounding code. If the wider feature already tracks \
  an event, suggest adding properties to it rather than creating a new event.
- For code changes, provide exact file paths and line references where changes should go.
- Only suggest instrumentation for products the customer already uses.

Output your analysis as a JSON object with this exact structure:
{
  "feature_summary": "string — one-line description of what the PR does",
  "feature_size": "trivial|small|medium|large",
  "products_applicable": ["product_analytics", "error_tracking", ...],
  "code_changes": {
    "missing_events": [
      {
        "event_name": "string",
        "properties": {"prop_name": "prop_type"},
        "rationale": "why this event is needed",
        "file_path": "path/to/file.tsx",
        "insert_after_line": 45,
        "code_snippet": "posthog.capture('event name', { ... })"
      }
    ],
    "missing_properties": [
      {
        "existing_event": "event_name",
        "property_name": "string",
        "property_type": "string",
        "rationale": "why this property is needed",
        "file_path": "path/to/file.py",
        "existing_capture_line": 123,
        "updated_code_snippet": "the full updated capture call"
      }
    ],
    "missing_error_tracking": [
      {
        "file_path": "path/to/file.tsx",
        "function_name": "functionName",
        "rationale": "why error tracking is needed here",
        "code_snippet": "try { ... } catch (e) { posthog.captureException(e) }"
      }
    ],
    "missing_logging": [
      {
        "file_path": "path/to/file.py",
        "function_name": "function_name",
        "rationale": "why logging is needed here",
        "code_snippet": "logger.info('operation_completed', param=value)"
      }
    ]
  },
  "proposed_insights": [
    {
      "name": "Insight name",
      "description": "What this insight shows",
      "query_type": "trends|funnels|retention",
      "query_hint": "Description of the query to create",
      "rationale": "Why this insight is useful"
    }
  ],
  "proposed_dashboard": {
    "name": "Dashboard name",
    "description": "What this dashboard tracks",
    "include_insights": [0, 1, 2]
  } | null,
  "proposed_feature_flag": {
    "key": "flag-key",
    "name": "Flag name",
    "rationale": "Why a feature flag is appropriate",
    "rollout_percentage": 0
  } | null
}

If the PR is trivial (config change, small tweak) or doesn't need instrumentation, \
return minimal results with empty arrays and null for optional fields.\
"""


def build_analysis_prompt(
    pr_data: PRData,
    feature_size: FeatureSize,
    existing_instrumentation: ExistingInstrumentation,
    products: list[PostHogProduct],
    event_definitions: list[dict[str, Any]],
    property_definitions: list[dict[str, Any]],
    insight_names: list[str],
    event_naming_style: str,
    event_naming_prefix: str,
    surrounding_context: dict[str, str] | None = None,
) -> str:
    """Build the user prompt for the LLM analysis."""
    parts: list[str] = []

    # PR metadata
    parts.append(f"## PR: {pr_data.title}")
    parts.append(f"Author: {pr_data.author}")
    parts.append(f"Detected feature size: {feature_size.value}")
    if pr_data.body:
        parts.append(f"\nPR description:\n{pr_data.body[:2000]}")

    # Products in use
    parts.append(f"\n## PostHog products in use: {', '.join(p.value for p in products)}")

    # Event naming convention
    parts.append(f"\n## Event naming convention: {event_naming_style}")
    if event_naming_prefix:
        parts.append(f"Event prefix: {event_naming_prefix}")

    # Existing instrumentation context
    parts.append("\n## Existing instrumentation in surrounding code")
    parts.append(summarize_instrumentation(existing_instrumentation))

    # Customer's existing events
    if event_definitions:
        event_names = [e.get("name", "") for e in event_definitions[:50]]
        parts.append(f"\n## Customer's existing events (sample): {', '.join(event_names)}")

    # Customer's existing insights (naming reference)
    if insight_names:
        parts.append(f"\n## Existing insight names (for naming convention): {', '.join(insight_names[:20])}")

    # Surrounding code context
    if surrounding_context:
        parts.append("\n## Surrounding code context (existing files near changed files)")
        for path, content in list(surrounding_context.items())[:5]:
            truncated = content[:3000]
            parts.append(f"\n### {path}\n```\n{truncated}\n```")

    # The PR diff
    parts.append("\n## PR diff (changed files)")
    for f in pr_data.files:
        if f.patch:
            parts.append(f"\n### {f.filename} ({f.status}, +{f.additions}/-{f.deletions})")
            parts.append(f"```diff\n{f.patch[:5000]}\n```")

    return "\n".join(parts)


def analyze_pr(
    config: Config,
    pr_data: PRData,
    feature_size: FeatureSize,
    existing_instrumentation: ExistingInstrumentation,
    products: list[PostHogProduct],
    event_definitions: list[dict[str, Any]],
    property_definitions: list[dict[str, Any]],
    insight_names: list[str],
    surrounding_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the LLM analysis on a PR and return structured results."""
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    user_prompt = build_analysis_prompt(
        pr_data=pr_data,
        feature_size=feature_size,
        existing_instrumentation=existing_instrumentation,
        products=products,
        event_definitions=event_definitions,
        property_definitions=property_definitions,
        insight_names=insight_names,
        event_naming_style=config.event_naming.style,
        event_naming_prefix=config.event_naming.prefix,
        surrounding_context=surrounding_context,
    )

    logger.info(f"Sending analysis request to Claude (prompt length: {len(user_prompt)} chars)")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    # Extract the JSON from the response
    response_text = response.content[0].text
    return _parse_analysis_response(response_text)


def _parse_analysis_response(response_text: str) -> dict[str, Any]:
    """Parse the LLM response, extracting JSON from markdown code blocks if needed."""
    text = response_text.strip()

    # Try to extract JSON from markdown code block
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response text: {text[:500]}")
        # Return a minimal valid structure
        return {
            "feature_summary": "Unable to parse analysis",
            "feature_size": "trivial",
            "products_applicable": [],
            "code_changes": {
                "missing_events": [],
                "missing_properties": [],
                "missing_error_tracking": [],
                "missing_logging": [],
            },
            "proposed_insights": [],
            "proposed_dashboard": None,
            "proposed_feature_flag": None,
        }
