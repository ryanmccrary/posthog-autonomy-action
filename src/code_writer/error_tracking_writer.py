from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorTrackingEdit:
    """A single error tracking edit to apply to a file."""

    file_path: str
    description: str
    anchor_line: str
    new_code: str
    import_line: str | None = None


def detect_error_tracking_pattern(file_content: str, file_path: str) -> str | None:
    """Detect which error tracking pattern the file or project uses.

    Checks most-specific patterns first to avoid generic matches.
    """
    if "posthog.captureException(" in file_content:
        return "posthog.captureException"
    if "Sentry.captureException(" in file_content:
        return "Sentry.captureException"
    if "capture_exception(" in file_content:
        return "capture_exception"
    if "captureException(" in file_content:
        return "captureException"
    return None


def build_try_catch_js(function_body: str, error_capture: str = "posthog.captureException(e)") -> str:
    """Wrap a JS function body in try/catch with error capture."""
    return f"""try {{
    {function_body}
}} catch (e) {{
    {error_capture}
    throw e
}}"""


def build_try_except_python(function_body: str, error_capture: str = "capture_exception(e)") -> str:
    """Wrap a Python function body in try/except with error capture."""
    return f"""try:
    {function_body}
except Exception as e:
    {error_capture}
    raise"""


def generate_error_tracking_edits(
    analysis: dict[str, Any],
    file_contents: dict[str, str],
) -> list[ErrorTrackingEdit]:
    """Generate concrete edits for missing error tracking."""
    edits: list[ErrorTrackingEdit] = []
    code_changes = analysis.get("code_changes", {})

    for item in code_changes.get("missing_error_tracking", []):
        file_path = item.get("file_path", "")
        if file_path not in file_contents:
            continue

        content = file_contents[file_path]
        import_line = None

        # Detect if we need to add an import
        existing_pattern = detect_error_tracking_pattern(content, file_path)
        if not existing_pattern:
            if file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                if "posthog" not in content.lower():
                    import_line = "import posthog from 'posthog-js'"
            elif file_path.endswith(".py"):
                if "capture_exception" not in content:
                    import_line = "from posthog.exceptions_capture import capture_exception"

        edits.append(
            ErrorTrackingEdit(
                file_path=file_path,
                description=(
                    f"Add error tracking to '{item.get('function_name', 'unknown')}' — {item.get('rationale', '')}"
                ),
                anchor_line="",
                new_code=item.get("code_snippet", ""),
                import_line=import_line,
            )
        )

    return edits
