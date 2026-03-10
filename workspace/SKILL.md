---
name: deploy-service-dfs
description: Execute intent-driven service operations in k8s_manager. Main flow is dependency-first deployment from natural language intent; also supports listing running services and listing available deployable services.
---

# Deploy Service DFS

Execute service-management intents directly using the `k8s_manager` HTTP API.

Do not generate code for the user. Execute the workflow.

**Testing** The API is currently at `http://test-api:8001`, this override any API endpoint mentioned in the API reference. 


## Capabilities

Understand natural-language intent and choose one capability:
  - `Deploy Services` with dependency resolution and user confirmation
  - `Show Running Services` inspect deployed instances according to the user's intent
  - `Inspect Deployable Services`: inspect deployable services, and show the information relevant to the user's intent



## Workflows by Capability


### Capability: Deploy Services (Main)

Inputs:
- `user_intent: string`
- Optional user-provided env hints (key/value pairs)
- `node_name: string | null` (optional)


Workflow:
1. Call `GET /info/services` but extract only service names, dependencies, and descriptions. Do not keep or return the full payload.
3. Select one or more initial services based on the relevance between user intent and service descriptions.
4. If no clear match, stop and ask user to clarify.
8. Start DFS from each initial service root. For each node:
  - Build env plan: Call `GET /info/services`, but only extract the object for this service, and return the required and optional envs. Then, use this metadata to fill the env values based on the user intents. Use known default values if not possible to guess from the intent.
  - Get a running instance with env values: Call `GET /status?name={service_name}`.
  - If already satisfied (service name matches, and every env variable value matches), skip the service.
  - If not satisfied, add the current service to `to_deploy` in post-order, and put its dependencies into the unsolved stack
12. Merge all DFS roots into one ordered, deduplicated plan.
13. Show to-be-deployed lists, then ask: `Proceed with deployment? (yes/no)`.
14. Do not continue unless user reply is affirmative.
15. If confirmed, deploy each service in order using `POST /instances`.
16. After each create, poll `GET /status/{instance_name}` until ready or timeout.
17. Stop on first failure and return partial results.

Determinism rules:
1. Sort dependency names alphabetically before traversal.
2. Canonicalize env vars before comparison:
   - Sort keys ascending.
   - Convert all values to string.
   - Build stable JSON object.

Readiness criteria:
- `deployment_status == "deployed"`
- all pods have `ready == true`
- all pod phases are `Running`

Failure handling:
- Dependency cycle during DFS: stop and report cycle.

Output:
- Intent decision result
- Selected initial service pool
- Ordered deployment plan
- Confirmation prompt
- Deployment result (including partial result on failure)

Final report format:
2. `Deployed` (`service_name`, `instance_name`)
3. `Failed` (first failing item and reason), if any
4. `Not executed due to failure` remaining items, if any

### Capability: Show Current Running Services

Workflow:
1. Call `GET /status`, or `GET /status?service_name={service_name}` if user intent is specific to a service.
2. Return concise per-instance list:
   - `instance_name`
   - `service_name`
   - `deployment_status`
   - pod readiness summary
   - all env vars
3. If `total == 0`, report no running/deployed services.

Output:
- Current deployed/running service instances

### Capability: List Deployable Services

Workflow:
1. Call `GET /info/services`.
2. Return concise per-service catalog:
   - `name`
   - `description`
   - direct `dependencies`
3. Include required/optional env schema summary when present.
4. Return `total`.

Output:
- Available deployable services with metadata

## API Reference

### Endpoint Configuration

Default base URL:
- `http://host.docker.internal:8001`

Treat base URL as runtime configuration. If endpoint changes, update before any call.

### Request Defaults

Use these defaults unless user specifies otherwise:
- `Content-Type: application/json` for request bodies
- `Accept: application/json`
- Timeout per request: `30s`
- Poll interval: `5s`
- Readiness timeout per instance: `300s`

Implementation rule:
- Use Python for API calls and response parsing.
- Do not use raw `curl` output as final response.

### Response Size Control

Required for all API calls:
- Parse JSON and extract only fields needed for the current step.
- Do not return or store full raw payload in agent output.
- Keep output compact and task-focused.


### Endpoints

#### `GET /info/services`

Purpose:
- Discover deployable services and metadata.

Use in workflows:
- Intent-to-service mapping
- Dependency graph creation
- Deployable catalog listing

Expected response fields:
- `services[].name`
- `services[].description`
- `services[].dependencies`
- `services[].required_env_vars`
- `services[].optional_env_vars`

NOTE: when you call this API in python, always add post-processing in your python code to extract only the fields or items that are relevant to the current step in the workloads. Do not return the full payload.

#### `GET /status`

Purpose:
- List current instances.

Use in workflows:
- Show running services
- Precheck env identity support (`env_hash` or `env_vars`)

Relevant response fields:
- `instances[].instance_name`
- `instances[].service_name`
- `instances[].deployment_status`
- `instances[].pods[].ready`
- `instances[].pods[].phase`
- `instances[].env
- `total`

#### `GET /status?service_name={service_name}`

Get the status instances filtered by service name. Useful for pre-checking if an instance with matching env already exists.

#### `POST /instances`

Purpose:
- Create a new service instance.

Example:

```json
{
  "service_name":  "lidar-object-counting",
  "node_name":     "node1-k8s",
  "env_vars": {
    "OBJECT_TYPE": "CAR",
    "ZONE_FILTER": "L10_all_e"
  }
}
```
