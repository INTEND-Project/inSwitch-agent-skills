"""Skill supervision tools."""

import os
import shutil
from datetime import datetime
from typing import Any, Dict

from core.fs import resolve_folder_abs
from core.logging_hub import log_event
from core.tools import tool, ToolContext


@tool(
    name="revise_skill",
    description=(
        "Revise a targeted /workspace SKILL.md after creating a mandatory "
        "backup. Captain-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "folder_path": {
                "type": "string",
                "description": "Folder path relative to /workspace.",
            },
            "new_content": {
                "type": "string",
                "description": "Complete replacement contents for SKILL.md.",
            },
            "change_summary": {
                "type": "string",
                "description": "Summary of the requested skill revision.",
            },
        },
        "required": ["folder_path", "new_content", "change_summary"],
    },
    captain_only=True,
)
def revise_skill(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    folder_path = args["folder_path"]
    new_content = args["new_content"]
    change_summary = args["change_summary"]

    try:
        folder_abs = resolve_folder_abs(folder_path)
    except Exception as exc:
        return {"error": str(exc)}

    skill_path = os.path.abspath(os.path.join(folder_abs, "SKILL.md"))
    workspace_root = os.path.abspath("/workspace")
    if not skill_path.startswith(workspace_root + os.sep):
        return {"error": "Target SKILL.md must be under /workspace."}

    backup_dir = os.path.join(folder_abs, ".skill_backups")
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = os.path.join(backup_dir, f"SKILL.{timestamp}.md")

    try:
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(skill_path, backup_path)
    except Exception as exc:
        return {"error": f"Failed to back up SKILL.md: {exc}"}

    try:
        with open(skill_path, "w", encoding="utf-8") as handle:
            handle.write(new_content)
    except Exception as exc:
        return {"error": f"Failed to write SKILL.md: {exc}"}

    log_event(
        "skill_revised",
        {
            "folder": folder_abs,
            "summary": change_summary,
            "backup_path": backup_path,
        },
    )
    return {"status": "ok", "path": skill_path, "backup_path": backup_path}
