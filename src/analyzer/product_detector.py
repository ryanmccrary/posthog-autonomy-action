from __future__ import annotations

import re
from enum import Enum


class PostHogProduct(str, Enum):
    PRODUCT_ANALYTICS = "product_analytics"
    ERROR_TRACKING = "error_tracking"
    LOGS = "logs"
    FEATURE_FLAGS = "feature_flags"
    LLM_ANALYTICS = "llm_analytics"


# Patterns that indicate each product is in use
PRODUCT_PATTERNS: dict[PostHogProduct, list[str]] = {
    PostHogProduct.PRODUCT_ANALYTICS: [
        r"posthog\.capture\(",
        r"posthoganalytics\.capture\(",
        r"report_user_action\(",
        r"usePostHog\(",
        r"posthog-js",
        r"posthog-python",
        r"posthog-node",
        r"posthog-ruby",
        r"PostHog::Client",
        r"\.capture\(\s*distinct_id:",  # Ruby PostHog SDK
        r"gem ['\"]posthog-ruby['\"]",
    ],
    PostHogProduct.ERROR_TRACKING: [
        r"captureException\(",
        r"posthog\.captureException\(",
        r"capture_exception\(",
        r"Sentry\.captureException\(",
        r"ErrorBoundary",
    ],
    PostHogProduct.LOGS: [
        r"structlog\.get_logger\(",
        r"logging\.getLogger\(",
        r"logger\.(info|warning|error|debug)\(",
        r"console\.(log|warn|error)\(",
        r"Rails\.logger\.",
        r"Logger\.new\(",
    ],
    PostHogProduct.FEATURE_FLAGS: [
        r"useFeatureFlag\(",
        r"posthog\.isFeatureEnabled\(",
        r"posthoganalytics\.feature_enabled\(",
        r"FEATURE_FLAGS\.",
        r"feature_flag",
    ],
    PostHogProduct.LLM_ANALYTICS: [
        r"openai\.",
        r"anthropic\.",
        r"@observe",
        r"langchain",
        r"llamaindex",
        r"llama_index",
        r"ChatCompletion",
        r"messages\.create\(",
    ],
}


def detect_products(code_content: str, explicit_products: list[str] | None = None) -> list[PostHogProduct]:
    """Detect which PostHog products are in use based on code patterns.

    If explicit_products is provided (from config), use those directly.
    Otherwise, auto-detect from code content.
    """
    if explicit_products:
        return [PostHogProduct(p) for p in explicit_products if p in PostHogProduct.__members__.values()]

    detected: list[PostHogProduct] = []
    for product, patterns in PRODUCT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, code_content):
                detected.append(product)
                break

    return detected


def detect_products_from_files(
    file_contents: dict[str, str],
    explicit_products: list[str] | None = None,
) -> list[PostHogProduct]:
    """Detect products from multiple file contents."""
    if explicit_products:
        results = []
        for p in explicit_products:
            try:
                results.append(PostHogProduct(p))
            except ValueError:
                pass
        return results

    all_content = "\n".join(file_contents.values())
    return detect_products(all_content)
