# Agent

A simple command-line agent that runs inside a container, uses the OpenAI API, and can call tools for shell access, Python execution, file I/O, and HTTP requests. It supports multi-agent delegation with a main coordinator ("captain") and named sub-agents.

## Setup

1) Create the API key file:

```
cd /agent
printf "YOUR_OPENAI_API_KEY" > openai.credential
```

2) (Optional) Set the model name:

```
export OPENAI_MODEL=gpt-5-mini
```

3) Make sure the host has the required mount points:

```
mkdir -p ./workspace ./logs
```

## Run with Docker Compose

Add the service in `docker-compose.yml` (already included in this repo), then:

```
docker compose up --build nerve-agent
```

The container runs in HTTP mode by default. You can also exec into the container and run the CLI mode manually.

```
docker compose exec nerve-agent python /agent/app.py
```

## HTTP API

```
POST http://localhost:8090/intent
Content-Type: application/json

{ "input": "your message" }
```

Response:

```
{ "response": "agent reply" }
```

Other endpoints:

```
GET http://localhost:8090/skills
GET http://localhost:8090/agents
```

## Skills

- The captain is bound to the root `/workspace` folder.
- Each agent is bound to a folder (relative to `/workspace`) and loads that folder's `SKILL.md` on startup.
- The agent does not scan subfolders for skills; it only uses the `SKILL.md` in its assigned folder.
- When a skill specifies compatibility requirements or setup steps, the agent must follow the setup instructions before executing tasks.
- Sub-agents are assigned to the same folder as the parent or a subfolder under it.

## Logs

- Logs are written to `/logs/YYYY-MM-DD.log` in JSON lines with timestamps.

## CLI commands

- `:help` show commands
- `:skills` print the current skills overview
- `:agents` list active agents
- `:kill <agent>` stop a sub-agent (captain cannot be killed)
- `:restart` kill all agents (including captain) and create a fresh captain
- `:exit` quit

`POST /intent` also supports command input. Example:

```json
{ "input": ":restart" }
```
