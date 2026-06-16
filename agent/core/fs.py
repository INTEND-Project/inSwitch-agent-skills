"""Filesystem helpers.

All path resolution goes through safe_abs_path to enforce that the agent
can only touch ALLOWED_ROOTS. Folder paths from skills are relative to
WORKSPACE_DIR; agent-scoped paths are relative to the agent's bound folder.
"""

import os
from typing import Optional, Protocol

from core.config import ALLOWED_ROOTS, WORKSPACE_DIR


class _HasFolderPath(Protocol):
    """Structural type for resolve_agent_path.

    Any object with a ``folder_path`` attribute is accepted; this lets fs
    stay independent of core.agent (which defines AgentState) and avoids
    an import cycle.
    """

    folder_path: Optional[str]


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def safe_abs_path(path: str) -> str:
    """Resolve ``path`` and ensure it lies within an allowed root.

    Raises ValueError if the resolved path escapes ALLOWED_ROOTS.
    """
    abs_path = os.path.abspath(path)
    for root in ALLOWED_ROOTS:
        root_abs = os.path.abspath(root)
        if abs_path == root_abs or abs_path.startswith(root_abs + os.sep):
            return abs_path
    allowed = ", ".join(ALLOWED_ROOTS)
    raise ValueError(f"Path must be within one of: {allowed}")


def normalize_folder_path(folder_path: str) -> str:
    """Normalize a workspace-relative folder path.

    Empty string becomes ".". Absolute paths and paths escaping the
    workspace raise ValueError.
    """
    if folder_path is None:
        raise ValueError("Folder path is required.")
    cleaned = folder_path.strip()
    if not cleaned:
        return "."
    if os.path.isabs(cleaned):
        raise ValueError("Folder path must be relative to /workspace.")
    norm = os.path.normpath(cleaned)
    if norm.startswith("..") or norm == "..":
        raise ValueError("Folder path must be within /workspace.")
    return norm


def resolve_folder_abs(folder_path: str) -> str:
    """Return the absolute path of a workspace-relative folder."""
    norm = normalize_folder_path(folder_path)
    return os.path.abspath(os.path.join(WORKSPACE_DIR, norm))


def resolve_agent_path(agent: _HasFolderPath, path: Optional[str]) -> str:
    """Resolve a path relative to the agent's bound folder.

    Absolute paths are validated against ALLOWED_ROOTS. Relative paths
    are joined with the agent's folder before validation.
    """
    base = resolve_folder_abs(agent.folder_path or ".")
    if not path:
        return base
    if os.path.isabs(path):
        return safe_abs_path(path)
    return safe_abs_path(os.path.join(base, path))


def list_folder_overview(folder_path: str) -> str:
    """Return a one-line summary of the folder's SKILL.md state."""
    folder_abs = resolve_folder_abs(folder_path)
    if not os.path.isdir(folder_abs):
        return f"No folder found: {folder_path}"

    current_skill = os.path.join(folder_abs, "SKILL.md")
    if os.path.isfile(current_skill):
        return "Current folder skill: SKILL.md present"
    return "Current folder skill: SKILL.md missing"