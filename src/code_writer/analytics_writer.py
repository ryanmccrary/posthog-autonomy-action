from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AnalyticsEdit:
    """A single analytics instrumentation edit to apply to a file."""

    file_path: str
    description: str
    # The line content after which to insert (for anchoring)
    anchor_line: str
    new_code: str
    # Optional import to add at the top of the file
    import_line: str | None = None


# Common import patterns for PostHog SDKs
JS_IMPORT_PATTERNS = {
    "posthog-js": "import posthog from 'posthog-js'",
    "posthog-node": "import { PostHog } from 'posthog-node'",
}

PYTHON_IMPORT_PATTERNS = {
    "posthoganalytics": "import posthoganalytics",
    "posthog": "from posthog import posthoganalytics",
}


def detect_capture_pattern(file_content: str, file_path: str) -> str | None:
    """Detect which PostHog capture pattern the file uses."""
    if "posthog.capture(" in file_content:
        return "posthog.capture"
    if "posthoganalytics.capture(" in file_content:
        return "posthoganalytics.capture"
    if "report_user_action(" in file_content:
        return "report_user_action"
    if "client.capture(" in file_content:
        return "client.capture"
    return None


def detect_existing_import(file_content: str) -> str | None:
    """Detect if PostHog is already imported."""
    if re.search(r"import posthog from", file_content):
        return "posthog-js"
    if re.search(r"from posthog-js", file_content):
        return "posthog-js"
    if re.search(r"import posthoganalytics", file_content):
        return "posthoganalytics"
    if re.search(r"from posthog", file_content):
        return "posthog"
    if re.search(r"usePostHog", file_content):
        return "posthog-js-react"
    return None


def build_capture_call_js(event_name: str, properties: dict[str, str]) -> str:
    """Build a JavaScript posthog.capture() call."""
    if not properties:
        return f"posthog.capture('{event_name}')"

    props_str = ", ".join(f"{k}" for k in properties.keys())
    return f"posthog.capture('{event_name}', {{ {props_str} }})"


def build_capture_call_python(event_name: str, properties: dict[str, str], distinct_id_var: str = "distinct_id") -> str:
    """Build a Python posthoganalytics.capture() call."""
    if not properties:
        return f"posthoganalytics.capture({distinct_id_var}, '{event_name}')"

    props_str = ", ".join(f"'{k}': {k}" for k in properties.keys())
    return f"posthoganalytics.capture({distinct_id_var}, '{event_name}', properties={{{props_str}}})"


def generate_analytics_edits(
    analysis: dict[str, Any],
    file_contents: dict[str, str],
) -> list[AnalyticsEdit]:
    """Generate concrete edits for missing analytics events and properties."""
    edits: list[AnalyticsEdit] = []
    code_changes = analysis.get("code_changes", {})

    # Missing events
    for event in code_changes.get("missing_events", []):
        file_path = event.get("file_path", "")
        if file_path not in file_contents:
            continue

        content = file_contents[file_path]
        import_line = None
        if not detect_existing_import(content):
            if file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                import_line = "import posthog from 'posthog-js'"
            elif file_path.endswith(".py"):
                import_line = "import posthoganalytics"

        edits.append(
            AnalyticsEdit(
                file_path=file_path,
                description=f"Add '{event['event_name']}' event — {event.get('rationale', '')}",
                anchor_line="",  # Will be refined by the code writer agent
                new_code=event.get("code_snippet", ""),
                import_line=import_line,
            )
        )

    # Missing properties on existing events
    for prop in code_changes.get("missing_properties", []):
        file_path = prop.get("file_path", "")
        if file_path not in file_contents:
            continue

        edits.append(
            AnalyticsEdit(
                file_path=file_path,
                description=(
                    f"Add '{prop['property_name']}' property to "
                    f"'{prop['existing_event']}' — {prop.get('rationale', '')}"
                ),
                anchor_line="",
                new_code=prop.get("updated_code_snippet", ""),
            )
        )

    return edits
