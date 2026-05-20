# Agent

A multi-agent system that runs inside a container, uses the OpenAI API, and calls local tools (shell, Python, files, HTTP) to fulfil user intents. A coordinator ("captain") delegates specialised subtasks to named sub-agents, each bound to a `/workspace` folder and a single `SKILL.md`.

## Architecture

The runtime is split across small modules under `core/`:

```
.
├── app.py                 Entrypoint shim → core.__main__:main
├── core/
│   ├── __init__.py
│   ├── __main__.py        Bootstrap: argparse, OpenAI client, manager,
│   │                      runner, then HTTP server or REPL.
│   ├── config.py          Environment-driven configuration.
│   ├── fs.py              Path resolution and safe access to
│   │                      /workspace, /agent, /logs.
│   ├── skills.py          SKILL.md parsing (frontmatter + sections).
│   ├── prompts.py         Captain and worker system-prompt builders.
│   ├── logging_hub.py     JSONL log file + SSE pub/sub.
│   ├── agent.py           AgentState, AgentManager, lifecycle helpers.
│   ├── runner.py          AgentTurnRunner: one turn = LLM call +
│   │                      tool-calling loop, instrumented for tracing.
│   ├── http_server.py     JSON API + /logs/stream SSE.
│   ├── cli.py             REPL with a :command registry.
│   └── tools/             Tool registry; each tool declares its JSON
│       ├── __init__.py    schema and implementation in one place.
│       ├── shell.py       run_shell, run_python
│       ├── files.py       read_file, write_file, list_dir
│       ├── http.py        http_request
│       └── delegation.py  delegate_task, list_agents (captain only)
├── tracing.py             Native tracing (SQLite, OTel-shaped).
├── trace_api.py           HTTP routes for trace inspection.
├── tests/
└── Dockerfile
```

### Extending the agent

- **Add a new tool**: drop a function decorated with `@tool(name=..., parameters=..., ...)` under `core/tools/`. The registry picks it up at import time.
- **Add a new CLI command**: write a function decorated with `@command(":name")` in `core/cli.py`.
- **Add a new HTTP route**: add a clause to `do_GET` or `do_POST` in `core/http_server.py`.
- **Add a domain skill**: place a folder with a `SKILL.md` under `/workspace`. The captain delegates to sub-agents that bind to that folder.

## Setup

1. Create the API key file:

```
cd /agent
printf "YOUR_OPENAI_API_KEY" > openai.credential
```

2. (Optional) Set the model name:

```
export OPENAI_MODEL=gpt-5-mini
```

3. Make sure the host has the required mount points:

```
mkdir -p ./workspace ./logs
```

## Run with Docker Compose

```
docker compose up --build agent
```

The container runs in HTTP mode by default. To use the CLI mode:

```
docker compose exec agent python /agent/app.py
```

## HTTP API

```
POST http://localhost:8085/intent
Content-Type: application/json

{ "input": "your message" }
```

Response:

```
{ "response": "agent reply", "trace_id": "..." }
```

Other endpoints:

```
GET  /skills                                    Workspace skill overview
GET  /agents                                    Active agent roster
GET  /logs/stream                               SSE feed of agent events
GET  /traces/{id}                               Inspect a trace
GET  /metrics/summary                           Aggregated trace metrics
GET  /metrics/timeseries?window=24h&bucket=hour Bucketed metrics
```

## Skills

- The captain is bound to the root `/workspace` folder.
- Each agent is bound to a folder (relative to `/workspace`) and loads that folder's `SKILL.md` on startup.
- The agent does not scan subfolders for skills; it only uses the `SKILL.md` in its assigned folder.
- When a skill specifies compatibility requirements or setup steps, the agent must follow the setup instructions before executing tasks.
- Sub-agents are assigned to the same folder as the parent or a subfolder under it.

## Logs

- JSONL lines written to `/logs/YYYY-MM-DD.log`.
- Live stream available at `GET /logs/stream` (Server-Sent Events).

## CLI commands

- `:help` show commands
- `:skills` print the current skills overview
- `:agents` list active agents
- `:kill <agent>` stop a sub-agent (captain cannot be killed)
- `:restart` kill all agents (including captain) and create a fresh captain
- `:verbose` toggle verbose tool output
- `:exit` / `:quit` quit

`POST /intent` also supports command input. Example:

```json
{ "input": ":restart" }
```
