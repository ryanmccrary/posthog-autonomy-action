from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CaptureCall:
    """Represents an existing posthog.capture() or similar call found in code."""

    file_path: str
    line_number: int
    event_name: str
    properties: list[str] = field(default_factory=list)
    raw_line: str = ""


@dataclass
class ErrorCapture:
    """Represents an existing captureException or error boundary."""

    file_path: str
    line_number: int
    pattern_type: str  # "captureException", "ErrorBoundary", "try_catch", etc.
    raw_line: str = ""


@dataclass
class LogStatement:
    """Represents an existing structured log statement."""

    file_path: str
    line_number: int
    level: str  # "info", "warning", "error", "debug"
    raw_line: str = ""


@dataclass
class ExistingInstrumentation:
    """Summary of existing instrumentation found in the codebase."""

    capture_calls: list[CaptureCall] = field(default_factory=list)
    error_captures: list[ErrorCapture] = field(default_factory=list)
    log_statements: list[LogStatement] = field(default_factory=list)
    feature_flag_checks: list[str] = field(default_factory=list)


# Regex patterns for finding instrumentation
CAPTURE_PATTERNS = [
    # posthog.capture('event_name', { props })  — JS/TS
    r"""(?:posthog|client)\.capture\(\s*['"]([\w\s\-\.]+)['"]""",
    # posthoganalytics.capture(distinct_id, 'event_name', properties={})  — Python
    r"""posthoganalytics\.capture\([^,]+,\s*['"]([\w\s\-\.]+)['"]""",
    # report_user_action(user, 'event_name')  — PostHog internal
    r"""report_user_action\([^,]+,\s*['"]([\w\s\-\.]+)['"]""",
]

# Order matters: more specific patterns first, so we match the best one per line
ERROR_PATTERNS = [
    (r"posthog\.captureException\(", "posthog.captureException"),
    (r"Sentry\.captureException\(", "Sentry.captureException"),
    (r"capture_exception\(", "capture_exception"),
    (r"captureException\(", "captureException"),
    (r"<ErrorBoundary", "ErrorBoundary"),
]

LOG_PATTERNS = [
    (r"logger\.(info)\(", "info"),
    (r"logger\.(warning)\(", "warning"),
    (r"logger\.(error)\(", "error"),
    (r"logger\.(debug)\(", "debug"),
    (r"log\.(info)\(", "info"),
    (r"log\.(warn)\(", "warning"),
    (r"log\.(error)\(", "error"),
]


def scan_file_for_instrumentation(file_path: str, content: str) -> ExistingInstrumentation:
    """Scan a single file for existing PostHog instrumentation."""
    result = ExistingInstrumentation()
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        # Check for capture calls
        for pattern in CAPTURE_PATTERNS:
            match = re.search(pattern, line)
            if match:
                result.capture_calls.append(
                    CaptureCall(
                        file_path=file_path,
                        line_number=i,
                        event_name=match.group(1),
                        raw_line=line.strip(),
                    )
                )

        # Check for error captures (first match wins — patterns are ordered most-specific-first)
        for pattern, pattern_type in ERROR_PATTERNS:
            if re.search(pattern, line):
                result.error_captures.append(
                    ErrorCapture(
                        file_path=file_path,
                        line_number=i,
                        pattern_type=pattern_type,
                        raw_line=line.strip(),
                    )
                )
                break

        # Check for log statements
        for pattern, level in LOG_PATTERNS:
            if re.search(pattern, line):
                result.log_statements.append(
                    LogStatement(
                        file_path=file_path,
                        line_number=i,
                        level=level,
                        raw_line=line.strip(),
                    )
                )

        # Check for feature flag usage
        ff_match = re.search(r"""(?:isFeatureEnabled|useFeatureFlag|feature_enabled)\(\s*['"]([\w\-]+)['"]""", line)
        if ff_match:
            result.feature_flag_checks.append(ff_match.group(1))

    return result


def merge_instrumentation(items: list[ExistingInstrumentation]) -> ExistingInstrumentation:
    """Merge multiple instrumentation scans into one."""
    merged = ExistingInstrumentation()
    for item in items:
        merged.capture_calls.extend(item.capture_calls)
        merged.error_captures.extend(item.error_captures)
        merged.log_statements.extend(item.log_statements)
        merged.feature_flag_checks.extend(item.feature_flag_checks)
    return merged


def summarize_instrumentation(instr: ExistingInstrumentation) -> str:
    """Create a text summary of existing instrumentation for use in LLM prompts."""
    parts: list[str] = []

    if instr.capture_calls:
        events = sorted(set(c.event_name for c in instr.capture_calls))
        parts.append(f"Existing analytics events ({len(events)}): {', '.join(events)}")

        for call in instr.capture_calls:
            parts.append(f"  - '{call.event_name}' in {call.file_path}:{call.line_number}")

    if instr.error_captures:
        types = sorted(set(e.pattern_type for e in instr.error_captures))
        parts.append(f"Existing error tracking patterns: {', '.join(types)}")

    if instr.log_statements:
        levels = sorted(set(stmt.level for stmt in instr.log_statements))
        parts.append(f"Existing logging ({len(instr.log_statements)} statements): levels used: {', '.join(levels)}")

    if instr.feature_flag_checks:
        flags = sorted(set(instr.feature_flag_checks))
        parts.append(f"Existing feature flag checks: {', '.join(flags)}")

    if not parts:
        return "No existing PostHog instrumentation found in surrounding code."

    return "\n".join(parts)
