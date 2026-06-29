"""Tool registry, dispatch, and shared execution context.

The original app.py defined tool schemas in one place (``tool_definitions``)
and their implementations in another (``dispatch_tool``), separated by
hundreds of lines. Adding a new tool meant editing two unrelated sections
and risking drift between schema and implementation.

This module replaces that pattern with a registry. Each tool lives in its
own file, decorated with ``@tool(...)``; the decorator records both the
JSON Schema (used to build the OpenAI tools list) and the callable
implementation in a single registry entry.

Public API:
    @tool(name, description, parameters, captain_only=False)
        Decorator that registers a tool implementation.

    ToolContext
        Dataclass passed to every tool. Carries the calling agent, the
        full agent map, the OpenAI client, the model name, the captain's
        verbosity flag, and the runner callable used by delegate_task.

    get_schemas(include_delegate: bool) -> list[dict]
        Returns the JSON Schema list to feed to OpenAI Responses API.

    dispatch(name: str, args: dict, ctx: ToolContext) -> dict
        Invokes the implementation registered under ``name`` with the
        given JSON arguments. Raises KeyError if the tool is unknown.

Tool implementation contract:
    Every tool is a function ``(args: dict, ctx: ToolContext) -> dict``.
    Reading defaults from ``args`` is the tool's responsibility (the
    registry does not validate the JSON against the schema; OpenAI does
    that on its side when emitting the call).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # AgentState lives in core.agent (extracted at commit 8). Forward-typed
    # here to avoid importing it eagerly — keeps this module self-contained
    # and breaks any future import cycle.
    from core.agent import AgentState


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------

@dataclass
class ToolContext:
    """Per-call execution context handed to every tool implementation.

    Fields:
        agent           The calling agent's state (folder_path, name, …).
        agents          The full agent map (read-only for most tools;
                        delegate_task mutates it).
        client          OpenAI client, for tools that need to spawn LLM
                        calls indirectly (delegate_task does, via runner).
        model           Model name to use when the tool spawns a sub-call.
        verbose         Captain's verbosity flag; some tools surface more
                        detail when enabled.
        runner          Callable that runs one agent turn end-to-end. Used
                        by delegate_task. Signature:
                          runner(agent, user_input, folder_overview,
                                 folder_skill, agents, verbose) -> str
                        At commit 7 this is the legacy run_agent_turn from
                        app.py; at commit 9 it becomes AgentTurnRunner.run.
        folder_overview Cached folder overview string for the calling agent.
        folder_skill    Cached SKILL.md content for the calling agent.
    """

    agent: "AgentState"
    agents: Dict[str, "AgentState"]
    client: Any
    model: str
    verbose: bool
    runner: Callable[..., str]
    folder_overview: str = ""
    folder_skill: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class _ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    impl: Callable[[Dict[str, Any], ToolContext], Dict[str, Any]]
    captain_only: bool = False

    def schema(self) -> Dict[str, Any]:
        """Return the JSON Schema entry consumed by the Responses API."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


_REGISTRY: Dict[str, _ToolSpec] = {}


def tool(
    *,
    name: str,
    description: str,
    parameters: Dict[str, Any],
    captain_only: bool = False,
) -> Callable[
    [Callable[[Dict[str, Any], ToolContext], Dict[str, Any]]],
    Callable[[Dict[str, Any], ToolContext], Dict[str, Any]],
]:
    """Register a tool implementation under ``name``.

    Use as a decorator on a function of signature
    ``(args: dict, ctx: ToolContext) -> dict``.

    Raises ValueError on duplicate registration so accidental collisions
    fail loudly at import time rather than silently overwriting.
    """

    def decorator(
        impl: Callable[[Dict[str, Any], ToolContext], Dict[str, Any]],
    ) -> Callable[[Dict[str, Any], ToolContext], Dict[str, Any]]:
        if name in _REGISTRY:
            raise ValueError(f"Tool already registered: {name}")
        _REGISTRY[name] = _ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            impl=impl,
            captain_only=captain_only,
        )
        return impl

    return decorator


# ---------------------------------------------------------------------------
# Public lookup helpers
# ---------------------------------------------------------------------------

def get_schemas(include_delegate: bool) -> List[Dict[str, Any]]:
    """Return the schema list for the OpenAI Responses ``tools`` parameter.

    ``include_delegate=True`` is used for the captain (which can spawn
    sub-agents); workers get the schema list with captain-only tools
    filtered out.
    """
    schemas: List[Dict[str, Any]] = []
    for spec in _REGISTRY.values():
        if spec.captain_only and not include_delegate:
            continue
        schemas.append(spec.schema())
    return schemas


def dispatch(name: str, args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Invoke the tool registered under ``name`` with JSON ``args``.

    Raises KeyError if no such tool exists. Per-tool errors are surfaced
    by the tool itself (typically as ``{"error": "..."}``) — this layer
    does not catch them.
    """
    spec = _REGISTRY.get(name)
    if spec is None:
        raise KeyError(f"Unknown tool: {name}")
    return spec.impl(args, ctx)


# Auto-import all tool modules so the registry is populated when callers
# do ``from core.tools import dispatch``. Listed explicitly (rather than
# via pkgutil) so the import graph is obvious from a grep.
from core.tools import shell, files, http, delegation, supervision  # noqa: E402,F401
