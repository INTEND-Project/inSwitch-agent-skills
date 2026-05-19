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

def run_agent_turn(
    client: OpenAI,
    agent: AgentState,
    user_input: str,
    folder_overview: str,
    folder_skill: str,
    agents: Dict[str, AgentState],
    verbose: bool,
) -> str:
    if agent.role == "captain":
        system_prompt = build_captain_prompt(folder_overview, folder_skill)
        tools = get_schemas(include_delegate=True)
    else:
        if not agent.folder_path or agent.folder_skill is None:
            return "Error: sub-agent is missing a folder."
        system_prompt = build_worker_prompt(
            agent.folder_path,
            agent.folder_skill,
            agent.name,
            folder_overview,
        )
        tools = get_schemas(include_delegate=False)

    # First LLM call for this turn
    with start_span("gen_ai.chat", {
        "gen_ai.request.model": MODEL,
        "agent.name": agent.name,
        "agent.role": agent.role,
    }) as span:
        try:
            response = client.responses.create(
                model=MODEL,
                input=[{"role": "user", "content": user_input}],
                instructions=system_prompt,
                tools=tools,
                previous_response_id=agent.last_response_id,
            )
        except Exception as exc:
            span.mark_error(f"OpenAI request failed: {exc}")
            return f"Error: OpenAI request failed: {exc}"

        if getattr(response, "usage", None):
            span.update({
                "gen_ai.usage.input_tokens": response.usage.input_tokens,
                "gen_ai.usage.output_tokens": response.usage.output_tokens,
                "gen_ai.usage.cost_usd": compute_llm_cost(MODEL, response.usage),
                "gen_ai.response_id": getattr(response, "id", None),
                "gen_ai.request_id": getattr(response, "_request_id", None),
            })

    while True:
        tool_calls = extract_tool_calls(response)
        if not tool_calls:
            break
        tool_outputs = []
        for call in tool_calls:
            call_id = getattr(call, "call_id", None) or getattr(call, "id", None)
            if not call_id:
                continue
            tool_name = getattr(call, "name", "")
            try:
                args = json.loads(getattr(call, "arguments", "") or "{}")
            except json.JSONDecodeError:
                args = {}
            log_event(
                "tool_invocation",
                {
                    "agent": agent.name,
                    "tool": tool_name,
                    "args": args,
                },
            )
            if verbose:
                print(f"\n[{agent.name} tool] {tool_name} args={args}")

            # Span per tool call
            with start_span("tool.call", {
                "tool.name": tool_name,
                "agent.name": agent.name,
            }) as tool_span:
                try:
                    ctx = ToolContext(
                        agent=agent,
                        agents=agents,
                        client=client,
                        model=MODEL,
                        verbose=verbose,
                        runner=run_agent_turn,
                        folder_overview=folder_overview,
                        folder_skill=folder_skill,
                    )
                    result = dispatch(tool_name, args, ctx)
                except Exception as exc:
                    result = {"error": str(exc)}
                    tool_span.mark_error(str(exc))

                if isinstance(result, dict) and "error" in result:
                    tool_span.mark_error(str(result["error"]))

            log_event(
                "tool_result",
                {
                    "agent": agent.name,
                    "tool": tool_name,
                    "result": result,
                },
            )
            if verbose:
                preview = json.dumps(result)
                if len(preview) > MAX_LOG_CHARS:
                    preview = preview[:MAX_LOG_CHARS] + "...(truncated)"
                print(f"[{agent.name} tool] output={preview}")
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                }
            )

        # Follow-up LLM call with tool outputs
        with start_span("gen_ai.chat", {
            "gen_ai.request.model": MODEL,
            "agent.name": agent.name,
            "agent.role": agent.role,
            "gen_ai.turn_kind": "tool_followup",
        }) as span:
            try:
                response = client.responses.create(
                    model=MODEL,
                    input=tool_outputs,
                    instructions=system_prompt,
                    tools=tools,
                    previous_response_id=response.id,
                )
            except Exception as exc:
                span.mark_error(f"OpenAI follow-up failed: {exc}")
                return f"Error: OpenAI follow-up failed: {exc}"

            if getattr(response, "usage", None):
                span.update({
                    "gen_ai.usage.input_tokens": response.usage.input_tokens,
                    "gen_ai.usage.output_tokens": response.usage.output_tokens,
                    "gen_ai.usage.cost_usd": compute_llm_cost(MODEL, response.usage),
                    "gen_ai.response_id": getattr(response, "id", None),
                    "gen_ai.request_id": getattr(response, "_request_id", None),
                })

    agent.last_response_id = response.id
    return extract_text(response) or "(no response)"

def process_user_input(manager: AgentManager, user_input: str) -> str:
    if user_input == ":restart":
        restart_result = restart_agent_session(manager, triggered_by="api")
        killed_agents = ", ".join(restart_result["killed_agents"])
        return f"Restarted agent session. Killed agents: {killed_agents}. Created clean captain."

    captain = manager.captain()
    if captain.folder_path is None:
        captain.folder_path = "."
    if captain.folder_skill is None:
        try:
            captain.folder_skill = load_folder_skill(captain.folder_path)
            captain.skill_name = extract_frontmatter_name(captain.folder_skill) or captain.folder_path
            log_event(
                "skill_loaded",
                {
                    "agent": captain.name,
                    "skill": captain.skill_name,
                },
            )
        except Exception as exc:
            captain.folder_skill = ""
            log_event(
                "skill_missing",
                {
                    "agent": captain.name,
                    "folder": captain.folder_path,
                    "error": str(exc),
                },
            )
    return run_agent_turn(
        client=manager.client,
        agent=captain,
        user_input=user_input,
        folder_overview=list_folder_overview(captain.folder_path),
        folder_skill=captain.folder_skill or "",
        agents=manager.agents,
        verbose=manager.verbose,
    )


class AgentHTTPRequestHandler(BaseHTTPRequestHandler):
    manager: AgentManager

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/intent":
            self._send_json(404, {"error": "Not found."})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return
        user_input = data.get("input")
        if not isinstance(user_input, str) or not user_input.strip():
            self._send_json(400, {"error": "Missing 'input' string."})
            return

        # Wrap the whole request in a root trace so every span created
        # during processing attaches underneath.
        with start_trace("agent.request", {
            "intent.text": user_input.strip()[:200],
        }) as handle:
            response_text = process_user_input(self.manager, user_input.strip())
            handle.set("response.length", len(response_text))

        self._send_json(200, {"response": response_text, "trace_id": handle.trace_id})

    def do_GET(self) -> None:
        if self.path == "/skills":
            self._send_json(200, {"skills": list_folder_overview(".")})
            return
        if self.path == "/agents":
            self._send_json(200, list_agents(self.manager.agents))
            return
        if self.path == "/logs/stream":
            self._handle_log_stream()
            return

        # Mount /traces, /traces/{id}, /metrics/summary, /metrics/timeseries
        if handle_trace_request(self.path, lambda code, body: self._send_json(code, body)):
            return

        self._send_json(404, {"error": "Not found."})

    def _handle_log_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        queue = LOG_STREAM_HUB.subscribe()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    message = queue.get(timeout=15)
                    safe_message = message.replace("\n", "\\n")
                    payload = f"data: {safe_message}\n\n".encode("utf-8")
                    self.wfile.write(payload)
                    self.wfile.flush()
                except Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            LOG_STREAM_HUB.unsubscribe(queue)

    def log_message(self, format: str, *args: Any) -> None:
        return


def extract_tool_calls(response: Any) -> List[Any]:
    calls = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", "") == "function_call":
            calls.append(item)
    return calls


def extract_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    parts = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", "") == "message":
            for content in getattr(item, "content", []):
                if getattr(content, "type", "") == "output_text":
                    parts.append(getattr(content, "text", ""))
    return "\n".join(parts).strip()


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

    if args.http:
        server = ThreadingHTTPServer((args.host, args.port), AgentHTTPRequestHandler)
        AgentHTTPRequestHandler.manager = manager
        print(f"Agent HTTP server on http://{args.host}:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
        return

    print("Agent ready. Type :help for commands.")
    print(f"Model: {MODEL}")

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input in {":exit", ":quit"}:
            print("Bye.")
            break
        if user_input == ":help":
            print("Commands: :help, :skills, :agents, :kill <agent>, :restart, :verbose, :exit")
            continue
        if user_input == ":skills":
            print(list_folder_overview("."))
            continue
        if user_input == ":agents":
            print(json.dumps(list_agents(agents), indent=2))
            continue
        if user_input.startswith(":kill "):
            target = user_input.split(" ", 1)[1].strip()
            if not target:
                print("Usage: :kill <agent_name>")
                continue
            if target == "captain":
                print("Cannot kill captain.")
                continue
            if target in agents:
                del agents[target]
                log_event(
                    "agent_killed",
                    {
                        "agent": target,
                        "killed_by": "user",
                    },
                )
                print(f"Killed agent: {target}")
            else:
                print(f"No such agent: {target}")
            continue
        if user_input == ":verbose":
            manager.verbose = not manager.verbose
            print(f"Verbose mode: {'on' if manager.verbose else 'off'}")
            continue
        if user_input == ":restart":
            restart_result = restart_agent_session(manager, triggered_by="user")
            killed_agents = ", ".join(restart_result["killed_agents"])
            print(f"Restarted agent session. Killed agents: {killed_agents}. Created clean captain.")
            continue

        # CLI interactive mode: wrap each input in a root trace too.
        with start_trace("agent.request", {
            "intent.text": user_input[:200],
            "source": "cli",
        }) as handle:
            text = process_user_input(manager, user_input)
            handle.set("response.length", len(text or ""))

        print(text or "(no response)")


if __name__ == "__main__":
    main()
