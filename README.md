# inSwitch Agent Skills

Lightweight multi-agent runtime with:
- A Python backend agent service (`agent/`)
- A React dashboard (`dashboard/`)
- Skill-driven behavior loaded from `workspace/SKILL.md` and subfolders

## 1) Install and Run with Docker Compose

Prerequisites:
- Docker + Docker Compose
- OpenAI API key

Set environment variable:

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

Important:
- Put all domain-specific skills under `workspace/`.
- The captain agent starts from `workspace/SKILL.md`.
- Sub-agent skills should live in subfolders under `workspace/` (each with its own `SKILL.md`).

Start services:

```bash
docker compose up --build
```

Access points:
- Agent API base: `http://localhost:8085`
- Dashboard: `http://localhost:8086`

Main API endpoints:
- `POST /intent` send user input to the captain agent
- `GET /skills` current folder skill overview
- `GET /agents` active agents
- `GET /logs/stream` server-sent event stream of logs

Example request:

```bash
curl -X POST http://localhost:8085/intent \
  -H "Content-Type: application/json" \
  -d '{"input":"hello"}'
```

## 2) Run Backend Locally

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_openai_api_key"
python app.py --http --host 0.0.0.0 --port 8085
```

Main agent API methods:
- `POST /intent`
  - Request: `{"input":"..."}`
  - Response: `{"response":"..."}`
- `GET /skills`
  - Response: skill status for current folder
- `GET /agents`
  - Response: list of active agents
- `GET /logs/stream`
  - Response: live SSE log stream for UI/observability

Notes:
- `OPENAI_MODEL` is optional (default: `gpt-5-mini`).
- Logs are written to `logs/YYYY-MM-DD.log` when using compose mounts.

## 3) Run Dashboard Locally

```bash
cd dashboard
yarn install
yarn dev
```

Local dashboard URL:
- `http://localhost:8091`

The dashboard expects backend API at `http://localhost:8085`.

Build production static files:

```bash
yarn build
```

## 4) Contributing

1. Fork/branch from `main`.
2. Keep changes scoped and documented.
3. Verify both backend and dashboard run locally.
4. Open a pull request with:
   - What changed
   - Why it changed
   - How it was tested

Recommended checks before PR:
- Backend starts and responds on `POST /intent`
- Dashboard loads and can send messages
- Docker Compose startup works end-to-end

## 5) Additional Notes

- License: MIT (`agent/LICENSE`).
- Runtime data locations (compose):
  - Skills/workspace: `./workspace -> /workspace`
  - Logs: `./logs -> /logs`
- If `OPENAI_API_KEY` is missing, backend startup fails by design.
