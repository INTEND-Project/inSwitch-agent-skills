"""Process entrypoint.

Wires up the components into a running agent. Reads OPENAI_API_KEY from
the environment, initialises the tracing DB and the agent manager, and
starts either the HTTP server (``--http``) or the interactive REPL.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict

from openai import OpenAI

from tracing import init_db as init_traces_db

from core.agent import AgentManager, AgentState, create_clean_captain
from core.cli import run_repl
from core.config import (
    HTTP_HOST_DEFAULT,
    HTTP_PORT_DEFAULT,
    MODEL,
    VERBOSE_DEFAULT,
)
from core.http_server import serve as serve_http
from core.logging_hub import LOG_STREAM_HUB
from core.runner import AgentTurnRunner


def load_api_key() -> str:
    """Read OPENAI_API_KEY from the environment.

    Raises ValueError when missing or empty so main() can print a
    helpful message and exit non-zero.
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set or empty."
        )
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent runner")
    parser.add_argument(
        "--http", action="store_true", help="Run as HTTP server"
    )
    parser.add_argument(
        "--host", default=HTTP_HOST_DEFAULT, help="HTTP host"
    )
    parser.add_argument(
        "--port", type=int, default=HTTP_PORT_DEFAULT, help="HTTP port"
    )
    args = parser.parse_args()

    try:
        api_key = load_api_key()
    except Exception as exc:
        print(f"Error: {exc}")
        print(
            "Set the OPENAI_API_KEY environment variable before "
            "starting the container."
        )
        sys.exit(1)

    # Initialize the tracing SQLite schema (idempotent).
    try:
        init_traces_db()
    except Exception as exc:
        print(f"Warning: could not initialize traces DB: {exc}")

    client = OpenAI(api_key=api_key)
    agents: Dict[str, AgentState] = {"captain": create_clean_captain()}
    manager = AgentManager(client=client, agents=agents, verbose=VERBOSE_DEFAULT)
    runner = AgentTurnRunner(
        client=client, model=MODEL, verbose=VERBOSE_DEFAULT
    )

    if args.http:
        serve_http(
            host=args.host,
            port=args.port,
            manager=manager,
            runner=runner,
            hub=LOG_STREAM_HUB,
        )
        return

    run_repl(manager, runner)


if __name__ == "__main__":
    main()