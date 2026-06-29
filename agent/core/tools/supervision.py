"""Skill supervision tools."""

import os
import shutil
from datetime import datetime
from typing import Any, Dict

from tracing import start_span

from core.agent import AgentState
from core.config import SUPERVISOR_DIR, WORKSPACE_DIR
from core.fs import normalize_folder_path, read_text_file, resolve_folder_abs
from core.logging_hub import log_event
from core.skills import extract_frontmatter_name, load_folder_skill
from core.tools import tool, ToolContext


def _resolve_workspace_skill(folder_path: str) -> tuple[str, str, str]:
    normalized_folder = normalize_folder_path(folder_path)
    folder_abs = resolve_folder_abs(normalized_folder)
    skill_path = os.path.abspath(os.path.join(folder_abs, "SKILL.md"))
    workspace_root = os.path.abspath(WORKSPACE_DIR)
    if not skill_path.startswith(workspace_root + os.sep):
        raise ValueError("Target SKILL.md must be under /workspace.")
    return normalized_folder, folder_abs, skill_path


@tool(
    name="read_skill",
    description=(
        "Read the current SKILL.md for a folder under /workspace. "
        "Folder paths must be relative to /workspace."
    ),
    parameters={
        "type": "object",
        "properties": {
            "folder_path": {
                "type": "string",
                "description": "Folder path relative to /workspace.",
            },
        },
        "required": ["folder_path"],
    },
    supervisor_allowed=True,
)
def read_skill(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    folder_path = args["folder_path"]
    try:
        normalized_folder, _, skill_path = _resolve_workspace_skill(
            folder_path
        )
        current_content = read_text_file(skill_path)
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "folder": normalized_folder,
        "path": skill_path,
        "content": current_content,
    }


@tool(
    name="revise_skill",
    description=(
        "Revise a targeted /workspace SKILL.md after creating a mandatory "
        "backup."
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
    supervisor_allowed=True,
)
def revise_skill(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    folder_path = args["folder_path"]
    new_content = args["new_content"]
    change_summary = args["change_summary"]

    try:
        normalized_folder, folder_abs, skill_path = _resolve_workspace_skill(
            folder_path
        )
        previous_content = read_text_file(skill_path)
    except Exception as exc:
        return {"error": str(exc)}

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

    invalidated_agents = 0
    for agent in ctx.agents.values():
        if agent.folder_path is None:
            continue
        try:
            agent_folder = normalize_folder_path(agent.folder_path)
        except Exception:
            continue
        if agent_folder != normalized_folder:
            continue
        agent.folder_skill = None
        agent.skill_name = None
        # Reset last_response_id so the old SKILL.md does not remain
        # implicitly available through the OpenAI previous_response_id chain.
        agent.last_response_id = None
        invalidated_agents += 1

    log_event(
        "skill_revised",
        {
            "folder": folder_abs,
            "summary": change_summary,
            "backup_path": backup_path,
        },
    )
    return {
        "status": "ok",
        "path": skill_path,
        "backup_path": backup_path,
        "previous_content": previous_content,
        "invalidated_agents": invalidated_agents,
    }


@tool(
    name="invoke_supervisor",
    description=(
        "Ask the supervisor agent to revise or improve a targeted SKILL.md "
        "according to a user-requested skill change. Captain-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "Skill change requested by the user.",
            },
        },
        "required": ["instruction"],
    },
    captain_only=True,
)
def invoke_supervisor(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if ctx.agent.role != "captain":
        return {"error": "Only the captain can invoke the supervisor."}

    instruction = args["instruction"]
    supervisor = ctx.agents.get("supervisor")
    new_supervisor = False
    if supervisor is None:
        supervisor = AgentState(
            name="supervisor",
            role="supervisor",
            folder_path=SUPERVISOR_DIR,
        )
        ctx.agents["supervisor"] = supervisor
        new_supervisor = True
    elif supervisor.role != "supervisor":
        return {"error": "Agent name 'supervisor' is already used."}

    if supervisor.folder_path != SUPERVISOR_DIR:
        supervisor.folder_path = SUPERVISOR_DIR
        supervisor.folder_skill = None
        supervisor.skill_name = None
        supervisor.last_response_id = None

    if new_supervisor:
        log_event(
            "agent_created",
            {
                "agent": supervisor.name,
                "created_by": ctx.agent.name,
                "folder": supervisor.folder_path,
                "role": supervisor.role,
            },
        )

    if supervisor.folder_skill is None:
        try:
            supervisor.folder_skill = load_folder_skill(supervisor.folder_path)
        except Exception as exc:
            if new_supervisor:
                del ctx.agents["supervisor"]
            return {"error": str(exc)}
        supervisor.skill_name = (
            extract_frontmatter_name(supervisor.folder_skill)
            or supervisor.folder_path
        )
        log_event(
            "skill_loaded",
            {"agent": supervisor.name, "skill": supervisor.skill_name},
        )

    log_event(
        "agent_message",
        {"from": ctx.agent.name, "to": supervisor.name, "content": instruction},
    )

    with start_span(
        "agent.turn",
        {
            "agent.name": "supervisor",
            "agent.role": "supervisor",
            "agent.skill": supervisor.skill_name or "",
            "agent.folder": supervisor.folder_path or "",
            "delegated_by": ctx.agent.name,
        },
    ):
        response_text = ctx.runner(
            agent=supervisor,
            user_input=instruction,
            folder_overview="Current folder skill: SKILL.md present",
            folder_skill=supervisor.folder_skill or "",
            agents=ctx.agents,
        )

    log_event(
        "agent_message",
        {"from": supervisor.name, "to": ctx.agent.name, "content": response_text},
    )
    return {"agent_name": supervisor.name, "response": response_text}
