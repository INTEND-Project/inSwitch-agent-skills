"""Agent state and lifecycle.

Two dataclasses sit at the heart of the runtime:

  - ``AgentState`` carries everything about one agent: its name, role
    (``captain``, ``worker``, or ``supervisor``), bound folder, cached
    SKILL.md content, and the previous OpenAI response id (for conversation
    continuity).

  - ``AgentManager`` owns the agent roster, the OpenAI client, and the
    runtime verbosity flag. It exposes ``captain()`` as a convenience
    because the captain is referenced from many code paths.

Two free functions complete the picture:

  - ``create_clean_captain`` builds a fresh captain bound to the workspace
    root.

  - ``restart_agent_session`` clears the roster, recreates the captain,
    and emits the matching ``agent_killed`` / ``agent_created`` /
    ``session_restarted`` events.

  - ``list_agents`` returns a JSON-serialisable summary of the roster, used
    by the HTTP ``/agents`` endpoint and the CLI ``:agents`` command.

  - ``is_within_parent`` checks that a child folder lies within a parent
    folder (used by delegate_task to scope sub-agents).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from core.fs import resolve_folder_abs
from core.logging_hub import log_event

if TYPE_CHECKING:
    # Typed only — the import would otherwise create a cycle through
    # the OpenAI module's heavy initialisation.
    from openai import OpenAI


@dataclass
class AgentState:
    """Mutable state for one agent.

    ``last_response_id`` is the OpenAI ``response.id`` from the previous
    turn; passing it to the next ``responses.create`` call lets the API
    chain context without us re-sending the whole transcript.

    ``folder_skill`` caches the SKILL.md content so we don't re-read it
    on every turn. Captain loads it lazily on first user input;
    delegate_task loads it on sub-agent creation.
    """

    name: str
    role: str
    last_response_id: Optional[str] = None
    folder_path: Optional[str] = None
    folder_skill: Optional[str] = None
    skill_name: Optional[str] = None


@dataclass
class AgentManager:
    """Process-wide agent roster.

    Holds the OpenAI client, the agent map (keyed by name), and the
    verbosity flag. ``captain()`` is a convenience accessor — the
    captain is always present at key ``"captain"``.
    """

    client: "OpenAI"
    agents: Dict[str, AgentState]
    verbose: bool

    def captain(self) -> AgentState:
        return self.agents["captain"]


def create_clean_captain() -> AgentState:
    """Return a fresh captain bound to the workspace root."""
    return AgentState(name="captain", role="captain", folder_path=".")


def restart_agent_session(
    manager: AgentManager, triggered_by: str
) -> Dict[str, Any]:
    """Kill every agent, recreate a clean captain, emit lifecycle events.

    Returns the list of killed agent names so callers (CLI / HTTP) can
    report it to the user.
    """
    killed_agents = sorted(manager.agents.keys())
    for agent_name in killed_agents:
        log_event(
            "agent_killed",
            {
                "agent": agent_name,
                "killed_by": triggered_by,
                "reason": "restart",
            },
        )
    manager.agents.clear()
    manager.agents["captain"] = create_clean_captain()
    log_event(
        "agent_created",
        {
            "agent": "captain",
            "created_by": triggered_by,
            "reason": "restart",
        },
    )
    log_event(
        "session_restarted",
        {
            "triggered_by": triggered_by,
            "killed_agents": killed_agents,
        },
    )
    return {"killed_agents": killed_agents}


def is_within_parent(parent_folder: str, child_folder: str) -> bool:
    """True if ``child_folder`` is the same as or under ``parent_folder``.

    Resolves both to absolute paths via ``resolve_folder_abs`` before
    comparing, so callers can pass any workspace-relative form.
    """
    parent_abs = resolve_folder_abs(parent_folder)
    child_abs = resolve_folder_abs(child_folder)
    if child_abs == parent_abs:
        return True
    return child_abs.startswith(parent_abs + os.sep)


def list_agents(agents: Dict[str, AgentState]) -> Dict[str, Any]:
    """Return a JSON-serialisable summary of the agent roster.

    Used by the HTTP ``/agents`` endpoint, the CLI ``:agents`` command,
    and the LLM-facing ``list_agents`` tool (via core.tools.delegation).
    """
    summary = []
    for name in sorted(agents.keys()):
        agent = agents[name]
        summary.append(
            {
                "name": agent.name,
                "role": agent.role,
                "folder": agent.folder_path,
            }
        )
    return {"agents": summary}
