"""Multi-agent delegation tools.

Two captain-only tools:

  - ``delegate_task`` spawns or reuses a sub-agent bound to a folder,
    loads its SKILL.md, and runs one turn via the runner provided in
    ToolContext. The recursive turn is wrapped in an ``agent.turn`` span
    so the trace tree reflects the captain → delegate → worker hierarchy.

  - ``list_agents_tool`` exposes the agent roster to the captain.

Both are filtered out of worker prompts via ``captain_only=True`` so a
sub-agent cannot itself delegate or introspect the roster.
"""

from typing import Any, Dict

from tracing import start_span

from core.agent import AgentState, is_within_parent, list_agents
from core.fs import list_folder_overview, normalize_folder_path
from core.logging_hub import log_event
from core.skills import extract_frontmatter_name, load_folder_skill
from core.tools import tool, ToolContext


@tool(
    name="delegate_task",
    description=(
        "Delegate a subtask to a named sub-agent assigned to a folder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Sub-agent name."},
            "folder_path": {
                "type": "string",
                "description": (
                    "Folder path relative to /workspace (same as or "
                    "under the parent folder)."
                ),
            },
            "task": {
                "type": "string",
                "description": "Task description for the sub-agent.",
            },
        },
        "required": ["agent_name", "folder_path", "task"],
    },
    captain_only=True,
)
def delegate_task(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    parent = ctx.agent
    if parent.role != "captain":
        return {"error": "Only the captain can delegate tasks."}

    agent_name = args["agent_name"]
    folder_path = args["folder_path"]
    task = args["task"]

    try:
        normalized_folder = normalize_folder_path(folder_path)
    except Exception as exc:
        return {"error": str(exc)}

    if not parent.folder_path:
        return {"error": "Captain is missing a folder."}
    if not is_within_parent(parent.folder_path, normalized_folder):
        return {
            "error": (
                "Folder must be the same as or a sub-folder of the "
                "parent folder."
            )
        }

    new_worker = False
    if agent_name in ctx.agents:
        worker = ctx.agents[agent_name]
        if worker.role != "worker":
            return {"error": "Agent name is already used by a non-worker."}
        if worker.folder_path and worker.folder_path != normalized_folder:
            return {
                "error": (
                    f"Agent '{agent_name}' is bound to folder "
                    f"'{worker.folder_path}'."
                )
            }
    else:
        worker = AgentState(name=agent_name, role="worker")
        ctx.agents[agent_name] = worker
        new_worker = True

    if worker.folder_path is None:
        worker.folder_path = normalized_folder

    if new_worker:
        log_event(
            "agent_created",
            {
                "agent": worker.name,
                "created_by": parent.name,
                "folder": worker.folder_path,
                "role": worker.role,
            },
        )

    if worker.folder_skill is None:
        try:
            worker.folder_skill = load_folder_skill(worker.folder_path)
        except Exception as exc:
            if new_worker:
                del ctx.agents[agent_name]
            return {"error": str(exc)}
        worker.skill_name = (
            extract_frontmatter_name(worker.folder_skill) or worker.folder_path
        )
        log_event(
            "skill_loaded",
            {"agent": worker.name, "skill": worker.skill_name},
        )

    log_event(
        "agent_message",
        {"from": parent.name, "to": worker.name, "content": task},
    )

    # Wrap the sub-agent's turn in a span so the trace tree reflects the
    # captain → delegate → worker hierarchy. Inner LLM and tool spans
    # nest under this one via contextvars.
    with start_span(
        "agent.turn",
        {
            "agent.name": worker.name,
            "agent.role": "worker",
            "agent.skill": worker.skill_name or "",
            "agent.folder": worker.folder_path or "",
            "delegated_by": parent.name,
        },
    ):
        response_text = ctx.runner(
            client=ctx.client,
            agent=worker,
            user_input=task,
            folder_overview=list_folder_overview(worker.folder_path),
            folder_skill=worker.folder_skill or "",
            agents=ctx.agents,
            verbose=ctx.verbose,
        )

    log_event(
        "agent_message",
        {"from": worker.name, "to": parent.name, "content": response_text},
    )
    return {"agent_name": worker.name, "response": response_text}


@tool(
    name="list_agents",
    description="List active agents and their assigned skills.",
    parameters={"type": "object", "properties": {}},
    captain_only=True,
)
def list_agents_tool(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """OpenAI-visible name is ``list_agents``; Python name differs to
    avoid colliding with core.agent.list_agents (the helper consumed by
    the HTTP ``/agents`` endpoint and the CLI ``:agents`` command).
    """
    return list_agents(ctx.agents)