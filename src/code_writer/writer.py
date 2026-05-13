from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

CODE_WRITER_SYSTEM_PROMPT = """\
You are a precise code editor that adds PostHog instrumentation to source files. \
You receive a list of instrumentation changes to apply and the current file contents. \
For each change, you produce an exact edit specification.

Rules:
- Only add instrumentation code (capture calls, error boundaries, logging). \
  NEVER modify business logic.
- Match the existing code style exactly (indentation, quotes, semicolons, etc.)
- Add imports at the top of the file if needed, following the file's existing import style
- Keep changes minimal — add only what's necessary
- If the file already has the instrumentation, skip it
- For each edit, provide the exact old_string to replace and the new_string

Output a JSON array of edits:
[
  {
    "file_path": "path/to/file.tsx",
    "edits": [
      {
        "description": "what this edit does",
        "old_string": "the exact existing code to find and replace",
        "new_string": "the replacement code (including the original code + new instrumentation)"
      }
    ]
  }
]

If a file needs an import added, include that as a separate edit at the top of the file.
If no changes are needed for a file, omit it from the output.\
"""


def apply_instrumentation_changes(
    anthropic_api_key: str,
    analysis: dict[str, Any],
    file_contents: dict[str, str],
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Use Claude to generate precise code edits for instrumentation changes.

    Returns a list of {file_path, edits: [{old_string, new_string}]} objects.
    """
    code_changes = analysis.get("code_changes", {})

    # Collect all changes that need to be applied
    all_changes: list[dict[str, Any]] = []
    all_changes.extend(code_changes.get("missing_events", []))
    all_changes.extend(code_changes.get("missing_properties", []))
    all_changes.extend(code_changes.get("missing_error_tracking", []))
    all_changes.extend(code_changes.get("missing_logging", []))

    if not all_changes:
        logger.info("No code changes to apply")
        return []

    # Build the prompt with file contents and requested changes
    prompt_parts: list[str] = []
    prompt_parts.append("## Changes to apply:")
    prompt_parts.append(json.dumps(all_changes, indent=2))

    prompt_parts.append("\n## Current file contents:")
    # Only include files that are referenced in changes
    referenced_files = set()
    for change in all_changes:
        fp = change.get("file_path", "")
        if fp:
            referenced_files.add(fp)

    for file_path in referenced_files:
        content = file_contents.get(file_path)
        if content is None:
            # Try to read from disk
            full_path = repo_root / file_path
            if full_path.exists():
                content = full_path.read_text()
        if content:
            prompt_parts.append(f"\n### {file_path}")
            prompt_parts.append(f"```\n{content[:8000]}\n```")

    client = anthropic.Anthropic(api_key=anthropic_api_key)

    logger.info(f"Requesting code edits for {len(all_changes)} changes across {len(referenced_files)} files")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=CODE_WRITER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": "\n".join(prompt_parts)},
        ],
    )

    response_text = response.content[0].text
    return _parse_edit_response(response_text)


def apply_edits_to_files(
    edits: list[dict[str, Any]],
    repo_root: Path,
) -> list[str]:
    """Apply the generated edits to files on disk. Returns list of modified file paths."""
    modified_files: list[str] = []

    for file_edit in edits:
        file_path = file_edit.get("file_path", "")
        full_path = repo_root / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            continue

        content = full_path.read_text()
        original_content = content

        for edit in file_edit.get("edits", []):
            old_string = edit.get("old_string", "")
            new_string = edit.get("new_string", "")

            if not old_string or not new_string:
                continue

            if old_string not in content:
                logger.warning(f"Could not find old_string in {file_path}: {old_string[:80]}...")
                continue

            # Only replace the first occurrence to be safe
            content = content.replace(old_string, new_string, 1)
            logger.info(f"Applied edit to {file_path}: {edit.get('description', 'no description')}")

        if content != original_content:
            full_path.write_text(content)
            modified_files.append(file_path)

    return modified_files


def _parse_edit_response(response_text: str) -> list[dict[str, Any]]:
    """Parse the LLM response containing edit specifications."""
    text = response_text.strip()

    # Extract JSON from markdown code block if present
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse code edit response: {e}")
        return []
