import argparse
import json
import os
import subprocess
import sys
import threading
from queue import Empty, Queue
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

from tracing import (
    start_trace,
    start_span,
    compute_llm_cost,
    init_db as init_traces_db,
)
from trace_api import handle_trace_request

from core.config import (
    CODE_DIR,
    WORKSPACE_DIR,
    LOGS_DIR,
    MODEL,
    VERBOSE_DEFAULT,
    MAX_LOG_CHARS,
    HTTP_HOST_DEFAULT,
    HTTP_PORT_DEFAULT,
    ALLOWED_ROOTS,
)

from core.fs import (
    read_text_file,
    safe_abs_path,
    normalize_folder_path,
    resolve_folder_abs,
    resolve_agent_path,
    list_folder_overview,
)

from core.skills import (
    parse_frontmatter,
    extract_frontmatter_description,
    extract_frontmatter_compatibility,
    extract_frontmatter_name,
    extract_setup_section,
    build_environment_notes,
    load_folder_skill,
)

from core.prompts import (
    base_system_prompt,
    build_captain_prompt,
    build_worker_prompt,
)

from core.logging_hub import LogStreamHub, LOG_STREAM_HUB, log_event

from core.agent import (
    AgentState,
    AgentManager,
    create_clean_captain,
    restart_agent_session,
    is_within_parent,
    list_agents,
)

from core.tools import ToolContext, dispatch, get_schemas

from core.runner import AgentTurnRunner
from core.http_server import serve as serve_http
from core.logging_hub import LOG_STREAM_HUB

from core.cli import run_repl

def load_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable is not set or empty.")
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent runner")
    parser.add_argument("--http", action="store_true", help="Run as HTTP server")
    parser.add_argument("--host", default=HTTP_HOST_DEFAULT, help="HTTP host")
    parser.add_argument("--port", type=int, default=HTTP_PORT_DEFAULT, help="HTTP port")
    args = parser.parse_args()

    try:
        api_key = load_api_key()
    except Exception as exc:
        print(f"Error: {exc}")
        print("Set the OPENAI_API_KEY environment variable before starting the container.")
        sys.exit(1)

    # Initialize the tracing SQLite schema (idempotent).
    try:
        init_traces_db()
    except Exception as exc:
        print(f"Warning: could not initialize traces DB: {exc}")

    client = OpenAI(api_key=api_key)
    agents: Dict[str, AgentState] = {"captain": create_clean_captain()}
    manager = AgentManager(client=client, agents=agents, verbose=VERBOSE_DEFAULT)
    runner = AgentTurnRunner(client=client, model=MODEL, verbose=VERBOSE_DEFAULT)

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
