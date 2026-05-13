from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LoggingEdit:
    """A single logging edit to apply to a file."""

    file_path: str
    description: str
    anchor_line: str
    new_code: str
    import_line: str | None = None


def detect_logging_pattern(file_content: str, file_path: str) -> str | None:
    """Detect which logging pattern the file uses."""
    if "structlog.get_logger(" in file_content:
        return "structlog"
    if "logging.getLogger(" in file_content:
        return "logging"
    if "logger = " in file_content and ".py" in file_path:
        return "logger_var"
    return None


def build_structlog_init() -> str:
    """Build structlog logger initialization."""
    return "logger = structlog.get_logger(__name__)"


def build_logging_init(module_name: str) -> str:
    """Build standard library logging initialization."""
    return f'logger = logging.getLogger("{module_name}")'


def generate_logging_edits(
    analysis: dict[str, Any],
    file_contents: dict[str, str],
) -> list[LoggingEdit]:
    """Generate concrete edits for missing logging."""
    edits: list[LoggingEdit] = []
    code_changes = analysis.get("code_changes", {})

    for item in code_changes.get("missing_logging", []):
        file_path = item.get("file_path", "")
        if file_path not in file_contents:
            continue

        content = file_contents[file_path]
        import_line = None

        # Detect if we need to add a logger import/init
        existing_pattern = detect_logging_pattern(content, file_path)
        if not existing_pattern and file_path.endswith(".py"):
            # Check if structlog is used elsewhere in the project
            import_line = "import structlog\n\nlogger = structlog.get_logger(__name__)"

        edits.append(
            LoggingEdit(
                file_path=file_path,
                description=f"Add logging to '{item.get('function_name', 'unknown')}' — {item.get('rationale', '')}",
                anchor_line="",
                new_code=item.get("code_snippet", ""),
                import_line=import_line,
            )
        )

    return edits
