"""Tests for the analyzer modules."""

from __future__ import annotations

import pytest

from src.analyzer.feature_classifier import FeatureSize, classify_feature_size, count_source_lines
from src.analyzer.instrumentation import (
    ExistingInstrumentation,
    merge_instrumentation,
    scan_file_for_instrumentation,
    summarize_instrumentation,
)
from src.analyzer.product_detector import PostHogProduct, detect_products, detect_products_from_files
from src.github_client import PRData, PRFile


class TestFeatureClassifier:
    @pytest.mark.parametrize(
        "additions,file_count,expected",
        [
            (3, 1, FeatureSize.TRIVIAL),
            (25, 2, FeatureSize.SMALL),
            (100, 5, FeatureSize.MEDIUM),
            (500, 15, FeatureSize.LARGE),
        ],
        ids=["trivial", "small", "medium", "large"],
    )
    def test_classify_feature_size(self, additions: int, file_count: int, expected: FeatureSize) -> None:
        files = [
            PRFile(
                filename=f"src/module{i}.ts",
                status="added",
                additions=additions // file_count,
            )
            for i in range(file_count)
        ]
        pr_data = PRData(
            number=1,
            title="test",
            body="",
            author="user",
            base_ref="main",
            head_ref="feature",
            head_sha="abc",
            files=files,
        )
        assert classify_feature_size(pr_data) == expected

    def test_count_source_lines_excludes_non_source(self) -> None:
        files = [
            PRFile(filename="src/app.ts", status="modified", additions=50, deletions=10),
            PRFile(filename="docs/readme.md", status="modified", additions=100, deletions=0),
            PRFile(filename="src/app.test.ts", status="modified", additions=30, deletions=5),
            PRFile(filename=".github/workflows/ci.yml", status="modified", additions=20, deletions=0),
        ]
        pr_data = PRData(
            number=1,
            title="test",
            body="",
            author="user",
            base_ref="main",
            head_ref="feature",
            head_sha="abc",
            files=files,
        )
        assert count_source_lines(pr_data) == 60  # Only src/app.ts


class TestProductDetector:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("posthog.capture('event')", [PostHogProduct.PRODUCT_ANALYTICS]),
            ("posthoganalytics.capture(uid, 'event')", [PostHogProduct.PRODUCT_ANALYTICS]),
            ("captureException(err)", [PostHogProduct.ERROR_TRACKING]),
            ("structlog.get_logger(__name__)", [PostHogProduct.LOGS]),
            ("useFeatureFlag('my-flag')", [PostHogProduct.FEATURE_FLAGS]),
            ("anthropic.messages.create(", [PostHogProduct.LLM_ANALYTICS]),
        ],
        ids=[
            "posthog-js-capture",
            "python-capture",
            "error-tracking",
            "structlog",
            "feature-flags",
            "llm-analytics",
        ],
    )
    def test_detect_products(self, code: str, expected: list[PostHogProduct]) -> None:
        assert detect_products(code) == expected

    def test_detect_multiple_products(self) -> None:
        code = """
        posthog.capture('event')
        captureException(err)
        logger.info('message')
        """
        products = detect_products(code)
        assert PostHogProduct.PRODUCT_ANALYTICS in products
        assert PostHogProduct.ERROR_TRACKING in products
        assert PostHogProduct.LOGS in products

    def test_explicit_products_override_detection(self) -> None:
        products = detect_products_from_files(
            {"file.ts": "posthog.capture('event')"},
            explicit_products=["error_tracking"],
        )
        assert products == [PostHogProduct.ERROR_TRACKING]


class TestInstrumentationScanner:
    def test_scan_capture_calls(self) -> None:
        content = """
import posthog from 'posthog-js'

function onSave() {
    posthog.capture('item saved', { item_type: 'widget' })
}

function onDelete() {
    posthog.capture('item deleted')
}
"""
        result = scan_file_for_instrumentation("src/app.ts", content)
        assert len(result.capture_calls) == 2
        assert result.capture_calls[0].event_name == "item saved"
        assert result.capture_calls[1].event_name == "item deleted"

    def test_scan_python_capture(self) -> None:
        content = """
import posthoganalytics

def create_widget(user, data):
    widget = Widget.objects.create(**data)
    posthoganalytics.capture(user.distinct_id, 'widget created', properties={'type': data['type']})
    return widget
"""
        result = scan_file_for_instrumentation("src/api.py", content)
        assert len(result.capture_calls) == 1
        assert result.capture_calls[0].event_name == "widget created"

    def test_scan_error_tracking(self) -> None:
        content = """
try {
    await fetchData()
} catch (e) {
    posthog.captureException(e)
    Sentry.captureException(e)
}
"""
        result = scan_file_for_instrumentation("src/api.ts", content)
        assert len(result.error_captures) == 2

    def test_scan_logging(self) -> None:
        content = """
import structlog

logger = structlog.get_logger(__name__)

def process():
    logger.info('processing started', count=10)
    logger.warning('slow operation')
    logger.error('processing failed')
"""
        result = scan_file_for_instrumentation("src/worker.py", content)
        assert len(result.log_statements) == 3

    def test_scan_feature_flags(self) -> None:
        content = """
const showNew = useFeatureFlag('new-dashboard')
if (posthog.isFeatureEnabled('beta-mode')) {
    // ...
}
"""
        result = scan_file_for_instrumentation("src/app.tsx", content)
        assert "new-dashboard" in result.feature_flag_checks
        assert "beta-mode" in result.feature_flag_checks

    def test_merge_instrumentation(self) -> None:
        a = ExistingInstrumentation(feature_flag_checks=["flag-a"])
        b = ExistingInstrumentation(feature_flag_checks=["flag-b"])
        merged = merge_instrumentation([a, b])
        assert set(merged.feature_flag_checks) == {"flag-a", "flag-b"}

    def test_summarize_empty(self) -> None:
        result = summarize_instrumentation(ExistingInstrumentation())
        assert "No existing PostHog instrumentation" in result

    def test_summarize_with_data(self) -> None:
        result = scan_file_for_instrumentation(
            "src/app.ts",
            "posthog.capture('test event')\nlogger.info('hello')",
        )
        summary = summarize_instrumentation(result)
        assert "test event" in summary
        assert "info" in summary
