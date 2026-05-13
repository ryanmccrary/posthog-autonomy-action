"""Tests for the code writer modules."""

from __future__ import annotations

import pytest

from src.code_writer.analytics_writer import (
    build_capture_call_js,
    build_capture_call_python,
    detect_capture_pattern,
    detect_existing_import,
    generate_analytics_edits,
)
from src.code_writer.error_tracking_writer import (
    detect_error_tracking_pattern,
    generate_error_tracking_edits,
)
from src.code_writer.logging_writer import (
    detect_logging_pattern,
    generate_logging_edits,
)
from src.code_writer.writer import _parse_edit_response


class TestAnalyticsWriter:
    def test_detect_capture_pattern_js(self) -> None:
        assert detect_capture_pattern("posthog.capture('e')", "a.ts") == "posthog.capture"

    def test_detect_capture_pattern_python(self) -> None:
        assert detect_capture_pattern("posthoganalytics.capture(uid, 'e')", "a.py") == "posthoganalytics.capture"

    def test_detect_capture_pattern_none(self) -> None:
        assert detect_capture_pattern("console.log('hello')", "a.ts") is None

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("import posthog from 'posthog-js'", "posthog-js"),
            ("import posthoganalytics", "posthoganalytics"),
            ("from posthog import something", "posthog"),
            ("const ph = usePostHog()", "posthog-js-react"),
            ("import React from 'react'", None),
        ],
        ids=["posthog-js", "posthoganalytics", "posthog-from", "react-hook", "none"],
    )
    def test_detect_existing_import(self, content: str, expected: str | None) -> None:
        assert detect_existing_import(content) == expected

    def test_build_capture_call_js_no_props(self) -> None:
        result = build_capture_call_js("button clicked", {})
        assert result == "posthog.capture('button clicked')"

    def test_build_capture_call_js_with_props(self) -> None:
        result = build_capture_call_js("button clicked", {"button_name": "string", "page": "string"})
        assert "posthog.capture('button clicked'" in result
        assert "button_name" in result

    def test_build_capture_call_python(self) -> None:
        result = build_capture_call_python("widget created", {"widget_type": "string"})
        assert "posthoganalytics.capture" in result
        assert "'widget created'" in result
        assert "'widget_type': widget_type" in result

    def test_generate_analytics_edits(self) -> None:
        analysis = {
            "code_changes": {
                "missing_events": [
                    {
                        "event_name": "batch trigger configured",
                        "properties": {"trigger_type": "string"},
                        "rationale": "Track batch trigger configuration",
                        "file_path": "src/app.ts",
                        "code_snippet": "posthog.capture('batch trigger configured', { trigger_type })",
                    }
                ],
                "missing_properties": [],
            }
        }
        file_contents = {"src/app.ts": "import posthog from 'posthog-js'\n\nfunction save() {}"}
        edits = generate_analytics_edits(analysis, file_contents)
        assert len(edits) == 1
        assert edits[0].file_path == "src/app.ts"
        assert edits[0].import_line is None  # Already imported

    def test_generate_analytics_edits_needs_import(self) -> None:
        analysis = {
            "code_changes": {
                "missing_events": [
                    {
                        "event_name": "test event",
                        "file_path": "src/new.ts",
                        "code_snippet": "posthog.capture('test event')",
                    }
                ],
                "missing_properties": [],
            }
        }
        file_contents = {"src/new.ts": "function doThing() {}"}
        edits = generate_analytics_edits(analysis, file_contents)
        assert len(edits) == 1
        assert edits[0].import_line == "import posthog from 'posthog-js'"


class TestErrorTrackingWriter:
    @pytest.mark.parametrize(
        "content,expected",
        [
            ("posthog.captureException(e)", "posthog.captureException"),
            ("captureException(err)", "captureException"),
            ("Sentry.captureException(e)", "Sentry.captureException"),
            ("capture_exception(e)", "capture_exception"),
            ("console.log('hello')", None),
        ],
        ids=["posthog", "generic", "sentry", "python", "none"],
    )
    def test_detect_error_tracking_pattern(self, content: str, expected: str | None) -> None:
        assert detect_error_tracking_pattern(content, "file.ts") == expected

    def test_generate_error_tracking_edits(self) -> None:
        analysis = {
            "code_changes": {
                "missing_error_tracking": [
                    {
                        "file_path": "src/api.ts",
                        "function_name": "fetchData",
                        "rationale": "Unhandled async",
                        "code_snippet": "try { await fetchData() } catch (e) { posthog.captureException(e) }",
                    }
                ]
            }
        }
        file_contents = {"src/api.ts": "import posthog from 'posthog-js'\nasync function fetchData() {}"}
        edits = generate_error_tracking_edits(analysis, file_contents)
        assert len(edits) == 1
        assert edits[0].import_line is None  # posthog already present


class TestLoggingWriter:
    @pytest.mark.parametrize(
        "content,file_path,expected",
        [
            ("structlog.get_logger(__name__)", "a.py", "structlog"),
            ("logging.getLogger(__name__)", "a.py", "logging"),
            ("logger = something", "a.py", "logger_var"),
            ("import React from 'react'", "a.tsx", None),
        ],
        ids=["structlog", "stdlib", "logger_var", "none"],
    )
    def test_detect_logging_pattern(self, content: str, file_path: str, expected: str | None) -> None:
        assert detect_logging_pattern(content, file_path) == expected

    def test_generate_logging_edits(self) -> None:
        analysis = {
            "code_changes": {
                "missing_logging": [
                    {
                        "file_path": "src/worker.py",
                        "function_name": "process_batch",
                        "rationale": "Data mutation without logging",
                        "code_snippet": "logger.info('batch_processed', count=len(items))",
                    }
                ]
            }
        }
        file_contents = {"src/worker.py": "def process_batch(items): pass"}
        edits = generate_logging_edits(analysis, file_contents)
        assert len(edits) == 1
        assert edits[0].import_line is not None  # Needs structlog import


class TestWriterParser:
    def test_parse_json_response(self) -> None:
        response = """```json
[
  {
    "file_path": "src/app.ts",
    "edits": [
      {
        "description": "Add capture call",
        "old_string": "function save() {",
        "new_string": "function save() {\\n    posthog.capture('item saved')"
      }
    ]
  }
]
```"""
        result = _parse_edit_response(response)
        assert len(result) == 1
        assert result[0]["file_path"] == "src/app.ts"

    def test_parse_plain_json_response(self) -> None:
        response = '[{"file_path": "a.ts", "edits": []}]'
        result = _parse_edit_response(response)
        assert len(result) == 1

    def test_parse_invalid_response(self) -> None:
        result = _parse_edit_response("not valid json at all")
        assert result == []
