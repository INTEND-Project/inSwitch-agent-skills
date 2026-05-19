"""File I/O tools: read_file, write_file, list_dir.

All paths are resolved through ``resolve_agent_path`` so relative inputs
are scoped to the calling agent's folder, and absolute inputs are still
validated against ALLOWED_ROOTS.
"""

import os
from typing import Any, Dict

from core.fs import read_text_file, resolve_agent_path
from core.tools import tool, ToolContext


@tool(
    name="read_file",
    description=(
        "Read a UTF-8 text file under /workspace, /agent, or /logs. "
        "Relative paths resolve from the agent's folder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
        },
        "required": ["path"],
    },
)
def read_file(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    path = args.get("path", "")
    abs_path = resolve_agent_path(ctx.agent, path)
    return {"content": read_text_file(abs_path)}


@tool(
    name="write_file",
    description=(
        "Write UTF-8 text to a file under /workspace, /agent, or /logs, "
        "creating directories if needed. Relative paths resolve from the "
        "agent's folder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
            "content": {"type": "string", "description": "File contents."},
        },
        "required": ["path", "content"],
    },
)
def write_file(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    path = args.get("path", "")
    content = args.get("content", "")
    abs_path = resolve_agent_path(ctx.agent, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return {"status": "ok", "path": abs_path}


@tool(
    name="list_dir",
    description=(
        "List files and directories under /workspace, /agent, or /logs. "
        "Relative paths resolve from the agent's folder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Directory path to list. Defaults to the agent's "
                    "folder under /workspace."
                ),
            }
        },
    },
)
def list_dir(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    # Same convention as the other file tools: resolve_agent_path returns
    # the agent's bound folder when path is None or empty.
    path = args.get("path")
    abs_path = resolve_agent_path(ctx.agent, path)
    entries = []
    for name in sorted(os.listdir(abs_path)):
        full_path = os.path.join(abs_path, name)
        entries.append(
            {"name": name, "type": "dir" if os.path.isdir(full_path) else "file"}
        )
    return {"path": abs_path, "entries": entries}