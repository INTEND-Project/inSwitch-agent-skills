---
name: deploy-service-dfs
description: Execute intent-driven, dependency-first deployment in k8s_manager. Start from a natural language intent, select one or more services from catalog descriptions, resolve dependencies, deduplicate by service+env, ask for confirmation, and deploy sequentially.
---

# Deploy Service DFS

Use this skill to run deployment directly, step by step, using the existing k8s_manager HTTP API.

Do not generate code for the user. Execute the workflow.

## Testing Assumption (Temporary, remove in production)

Use this section only for current testing. Remove it when real APIs are available.

- There is no live API endpoint yet.
- Simulate `GET /info/services` by loading data from `/resource/service-info.json`.
- Simulate `GET /status` as if only one service is already deployed:
  - `osef-tracked-objects`
- Simulate deployments (`POST /instances`) as always successful.
- Simulate readiness checks (`GET /status/{instance_name}`) as successful for every created instance.

## Inputs

- `deployment_intent: string` (natural language goal)
- Optional user-provided env hints (key/value pairs)
- `node_name: string | null` (optional)
- `resolve_dep_env` policy for each dependency (must be deterministic)

## Output

- Selected initial service pool from intent (one or more services)
- Ordered plan: dependencies first, dependents later
- Confirmation prompt showing what will be deployed
- Deployment result: skipped/already-present, created instances, failures

## Runtime Rules

- Always ask for confirmation before any `POST /instances`.
- Stop on first deployment failure.
- Do not auto-delete already created dependencies on failure unless user asks.
- Keep behavior deterministic:
1. Sort dependency names alphabetically before traversal.
2. Canonicalize env vars before comparison (see below).

## Prechecks

- The API must expose env identity in status (`env_hash` preferred, `env_vars` acceptable).
- If status payload has neither `env_hash` nor `env_vars`, stop and report that safe deduplication is impossible.

## Canonicalization

Canonicalize desired env vars before every dedup check:
1. Sort keys ascending.
2. Convert all values to string.
3. Build stable JSON object.
4. Compute fingerprint hash from that canonical JSON.

Use this fingerprint for dedup identity checks.

## API Call Contract

Use these defaults unless user specifies otherwise:
- `Content-Type: application/json` for request bodies
- `Accept: application/json`
- Base URL: user-provided API host (for example `http://localhost:8000`)
- Timeout per request: 30s
- Poll interval for readiness: 5s
- Readiness timeout per instance: 300s

### 1) Discover service catalog and dependency graph

```http
GET /info/services
```

Expected response shape (relevant fields):
```json
{
  "services": [
    {
      "name": "service-a",
      "description": "Detects objects crossing configured zones",
      "dependencies": ["service-b", "service-c"]
    }
  ],
  "total": 1
}
```

Agent actions:
- Build:
  - `deps_map` from `services[].name -> services[].dependencies`
  - `catalog` from `name + description + env schema` for service selection and env planning

### 2) Select initial service pool from intent

Inputs:
- `deployment_intent`
- `/info/services` descriptions

Selection rules:
1. Choose all services whose descriptions clearly match the intent.
2. Allow multiple initial services when intent requests multiple capabilities.
3. If no clear match exists, stop and ask user to clarify intent.
4. If ambiguous matches exist, present top candidates and ask user to confirm selection.

Result:
- `initial_services = [{service_name, env_vars}]`
- These are starting nodes for dependency resolution.

Env planning rule:
- Start from user-provided env hints.
- Fill known defaults from service metadata when available.
- If required env values are missing, ask user before deployment.

### 3) Check if service+env is already deployed

```http
GET /status?name={service_name}
```

Expected response shape (relevant fields):
```json
{
  "instances": [
    {
      "instance_name": "service-a-abc12345",
      "service_name": "service-a",
      "env_hash": "sha256:...",
      "env_vars": {"KEY_1":"value1"},
      "deployment_status": "deployed",
      "pods": [{"ready": true, "phase": "Running"}]
    }
  ]
}
```

Dedup decision:
- Prefer `env_hash` exact match.
- If `env_hash` missing, canonicalize and compare `env_vars` exactly.
- Exact match means "already satisfied", so do not add to deploy plan.

### 4) Create instance

```http
POST /instances
Content-Type: application/json

{
  "service_name": "service-a",
  "env_vars": {
    "KEY_1": "value1",
    "KEY_2": "value2"
  },
  "node_name": "node1-k8s"
}
```

Success (`201`):
```json
{
  "instance_name": "service-a-abc12345",
  "service_name": "service-a",
  "namespace": "default",
  "image": "registry/...:latest"
}
```

### 5) Poll readiness for created instance

```http
GET /status/{instance_name}
```

Success criteria:
- `deployment_status == "deployed"`
- all returned pods have `ready == true`
- pod phase should be `Running` for all pods

## Error Handling Rules

- `GET /info/services` non-2xx: stop immediately.
- `GET /status` non-2xx for dedup check: stop immediately (cannot safely continue).
- `POST /instances` `409`: run one dedup re-check (`GET /status?name={service}`):
1. if matching env now exists, mark as skipped (concurrent create won race)
2. if no matching env, treat as failure and stop
- `POST /instances` other non-2xx: stop and report.
- `GET /status/{instance_name}` polling timeout: stop and report.
- Dependency cycle detected during DFS: stop and report cycle.

## Execution Workflow (Agent Action Plan)

1. Call `GET /info/services`; build `catalog` and `deps_map`.
2. Map `deployment_intent` to one or more initial services using service descriptions.
3. Build env values for each initial service (hints + defaults + required-value check).
4. Start DFS from each initial service node.
5. For each node in DFS, run dedup check via `GET /status?name={service}`.
6. If not already deployed, recurse into dependencies first.
7. After dependencies are processed, add current service+env to `to_deploy` (post-order).
8. After all DFS roots complete, merge into one ordered, deduplicated plan.
9. Show selected initial services, skipped items, and final `to_deploy`; ask user confirmation.
10. If confirmed, deploy each item in order with `POST /instances`.
11. After each create, poll `GET /status/{instance_name}` until ready or timeout.
12. Stop on first failure; return partial results.

## Confirmation Message Template

Show before deployment:
1. `Skipped (already deployed)` entries
2. `To Deploy (ordered)` entries
3. Explicit question: `Proceed with deployment? (yes/no)`

Do not continue unless user reply is affirmative.

## Final Report Template

Return:
1. `Skipped` (already satisfied by existing deployment)
2. `Deployed` (`service_name`, `instance_name`)
3. `Failed` (first failing item and reason), if any
4. `Not executed due to failure` remaining plan items, if any
