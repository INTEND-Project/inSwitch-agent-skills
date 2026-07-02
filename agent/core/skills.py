"""SKILL.md parsing and environment-note building.

A SKILL.md file is a Markdown document with an optional YAML-like frontmatter
block delimited by ``---``. The frontmatter holds metadata (name, description,
compatibility, …); the body may contain a top-level ``## Setup`` section with
environment preparation steps.

We parse the frontmatter with a minimal hand-rolled scanner — no external YAML
dependency — supporting:
  - inline values:       ``key: value`` (with optional single/double quotes)
  - literal blocks:      ``key: |`` followed by indented lines (newlines kept)
  - folded blocks:       ``key: >`` followed by indented lines (newlines folded
                         into spaces)
"""

import os
from typing import Dict, List

from core.fs import resolve_folder_abs, read_text_file, safe_abs_path


def parse_frontmatter(skill_text: str) -> Dict[str, str]:
    """Parse the YAML-ish frontmatter block of a SKILL.md text.

    Returns a dict mapping each top-level key to its string value. Missing
    frontmatter (no opening ``---`` on the first line) yields an empty dict.
    Unknown keys are preserved; callers can read whatever they need.
    """
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    result: Dict[str, str] = {}
    idx = 1
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "---":
            break

        if ":" not in line:
            idx += 1
            continue

        key, raw = line.split(":", 1)
        # Only treat top-level (non-indented) keys as fields.
        if key.startswith(" ") or key.startswith("\t"):
            idx += 1
            continue
        key = key.strip()
        raw = raw.strip()

        if raw in {"|", ">"}:
            block_lines, idx = _read_indented_block(lines, idx + 1)
            if raw == ">":
                result[key] = " ".join(s.strip() for s in block_lines).strip()
            else:
                result[key] = "\n".join(block_lines).strip()
            continue

        # Inline scalar: strip surrounding quotes if present.
        result[key] = raw.strip('"').strip("'")
        idx += 1

    return result


def _read_indented_block(lines: List[str], start_idx: int) -> tuple[List[str], int]:
    """Read consecutive indented lines starting at ``start_idx``.

    Stops on the closing ``---`` or the first non-indented, non-empty line.
    Returns the (left-stripped) block lines and the index of the first line
    that was not consumed.
    """
    block: List[str] = []
    idx = start_idx
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "---":
            break
        if line.startswith(" ") or line.startswith("\t"):
            block.append(line.lstrip())
            idx += 1
            continue
        break
    return block, idx


# ---------------------------------------------------------------------------
# Thin convenience accessors — kept for backwards compatibility with the
# original app.py API. Internally they just consult the frontmatter dict.
# ---------------------------------------------------------------------------

def extract_frontmatter_description(skill_text: str) -> str:
    return parse_frontmatter(skill_text).get("description", "")


def extract_frontmatter_compatibility(skill_text: str) -> str:
    return parse_frontmatter(skill_text).get("compatibility", "")


def extract_frontmatter_name(skill_text: str) -> str:
    return parse_frontmatter(skill_text).get("name", "")


# ---------------------------------------------------------------------------
# Body sections
# ---------------------------------------------------------------------------

def extract_setup_section(skill_text: str) -> str:
    """Return the verbatim ``## Setup`` section (header included), or ""."""
    lines = skill_text.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            title = line[3:].strip().lower()
            if title == "setup" or title.startswith("setup:"):
                start_idx = idx
                break
    if start_idx is None:
        return ""

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].startswith("## "):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx]).strip()


def build_environment_notes(skill_text: str) -> str:
    """Concatenate compatibility + setup into a single prompt-ready blob."""
    compatibility = extract_frontmatter_compatibility(skill_text)
    setup = extract_setup_section(skill_text)
    notes: List[str] = []
    if compatibility:
        notes.append("Compatibility requirements:\n" + compatibility)
    if setup:
        notes.append(
            "Setup instructions (follow on skill load if needed):\n" + setup
        )
    return "\n\n".join(notes)


def load_folder_skill(folder_path: str) -> str:
    """Read the SKILL.md from a workspace-relative or allowed absolute folder.

    Raises FileNotFoundError if no SKILL.md is present.
    """
    if os.path.isabs(folder_path):
        folder_abs = safe_abs_path(folder_path)
    else:
        folder_abs = resolve_folder_abs(folder_path)
    skill_file = os.path.join(folder_abs, "SKILL.md")
    if not os.path.isfile(skill_file):
        raise FileNotFoundError(f"SKILL.md not found in folder: {folder_path}")
    return read_text_file(skill_file)
