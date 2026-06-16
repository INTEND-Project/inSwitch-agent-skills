"""Command-line REPL.

The CLI is a small command registry plus a read-eval loop. Commands
start with ``:`` and are dispatched through ``_COMMANDS``; anything
else is treated as a user intent and forwarded to the runner.

Adding a new command is a one-liner: define a function decorated with
``@command(":name")``. The decorator records it in the registry and
``run_repl`` finds it automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Dict, TYPE_CHECKING

from tracing import start_trace

from core.agent import list_agents, restart_agent_session
from core.fs import list_folder_overview
from core.logging_hub import log_event

if TYPE_CHECKING:
    from core.agent import AgentManager
    from core.runner import AgentTurnRunner


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class CliContext:
    """Per-REPL execution context handed to every command."""

    manager: "AgentManager"
    runner: "AgentTurnRunner"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Each command returns True to keep the REPL going, False to exit.
_CommandFn = Callable[[CliContext, str], bool]

_COMMANDS: Dict[str, _CommandFn] = {}


def command(name: str) -> Callable[[_CommandFn], _CommandFn]:
    """Register a function under the given command name (e.g. ``:help``).

    Raises ValueError on duplicate registration so import-time
    collisions fail loudly.
    """

    def decorator(fn: _CommandFn) -> _CommandFn:
        if name in _COMMANDS:
            raise ValueError(f"Command already registered: {name}")
        _COMMANDS[name] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@command(":help")
def cmd_help(ctx: CliContext, args: str) -> bool:
    print(
        "Commands: :help, :skills, :agents, :kill <agent>, :restart, "
        ":verbose, :exit"
    )
    return True


@command(":skills")
def cmd_skills(ctx: CliContext, args: str) -> bool:
    print(list_folder_overview("."))
    return True


@command(":agents")
def cmd_agents(ctx: CliContext, args: str) -> bool:
    print(json.dumps(list_agents(ctx.manager.agents), indent=2))
    return True


@command(":kill")
def cmd_kill(ctx: CliContext, args: str) -> bool:
    target = args.strip()
    if not target:
        print("Usage: :kill <agent_name>")
        return True
    if target == "captain":
        print("Cannot kill captain.")
        return True
    if target in ctx.manager.agents:
        del ctx.manager.agents[target]
        log_event("agent_killed", {"agent": target, "killed_by": "user"})
        print(f"Killed agent: {target}")
    else:
        print(f"No such agent: {target}")
    return True


@command(":verbose")
def cmd_verbose(ctx: CliContext, args: str) -> bool:
    ctx.manager.verbose = not ctx.manager.verbose
    # Keep the runner in sync so subsequent turns see the new flag.
    ctx.runner.verbose = ctx.manager.verbose
    print(f"Verbose mode: {'on' if ctx.manager.verbose else 'off'}")
    return True


@command(":restart")
def cmd_restart(ctx: CliContext, args: str) -> bool:
    result = restart_agent_session(ctx.manager, triggered_by="user")
    killed = ", ".join(result["killed_agents"])
    print(
        f"Restarted agent session. Killed agents: {killed}. "
        "Created clean captain."
    )
    return True


@command(":exit")
def cmd_exit(ctx: CliContext, args: str) -> bool:
    print("Bye.")
    return False


# Alias — same handler, separate registry entry to avoid silent surprises
# if one day :exit and :quit diverge.
@command(":quit")
def cmd_quit(ctx: CliContext, args: str) -> bool:
    print("Bye.")
    return False


# ---------------------------------------------------------------------------
# REPL loop
# ---------------------------------------------------------------------------

def run_repl(manager: "AgentManager", runner: "AgentTurnRunner") -> None:
    """Interactive read-eval loop.

    Lines starting with ``:`` are dispatched through the command
    registry; anything else is wrapped in a root trace and forwarded
    to ``runner.process_user_input``.
    """
    ctx = CliContext(manager=manager, runner=runner)

    print("Agent ready. Type :help for commands.")
    print(f"Model: {runner.model}")

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not user_input:
            continue

        # Command: split on first space, dispatch on the head.
        if user_input.startswith(":"):
            head, _, tail = user_input.partition(" ")
            fn = _COMMANDS.get(head)
            if fn is None:
                print(f"Unknown command: {head}. Type :help for the list.")
                continue
            if not fn(ctx, tail):
                return
            continue

        # User intent: forward to the runner under a root trace.
        with start_trace(
            "agent.request",
            {"intent.text": user_input[:200], "source": "cli"},
        ) as handle:
            text = runner.process_user_input(manager, user_input)
            handle.set("response.length", len(text or ""))

        print(text or "(no response)")