#SKILL.md

This skill explains how to use the simulated Nerve API to manage FILL machine data analytics. 
The APIs can be used to check and manage machine nodes, workloads/versions, and deploy or undeploy
workload versions via DNA target configuration.

Sample URL (local): `http://<host>:3000` Ask host (and port) before starting.

## How to use the API to deploy workloads

If the input is a list of workload:version entries, use "Deploy or undeploy via DNA target" section, to generate YAML payload and call "apply target".

If the input is only a list of workloads (no versions provided), use "workload version" APIs to get the first version of the workload, and then "apply target".

## Nodes: list, create, update state, delete

List all nodes (optionally filter by serial number):
```http
GET /nerve/nodes/list
GET /nerve/nodes/list?serialNumber=SN1234
```

Get a single node by serial number:
```http
GET /nerve/node/{serialNumber}
```

Create a node:
```http
POST /nerve/node
Content-Type: application/json

{
  "name": "node-01",
  "model": "TTTech-R1",
  "serialNumber": "SN1234",
  "secureId": "SEC1234",
  "labels": ["factory", "lineA"],
  "state": "ONLINE"
}
```

Update node state (ONLINE/OFFLINE):
```http
PUT /nerve/node/{serialNumber}/state
Content-Type: application/json

{
  "state": "OFFLINE"
}
```

Delete a node:
```http
DELETE /nerve/node/{serialNumber}
```

## Workloads: list, create, delete

List workloads:
```http
GET /nerve/v3/workloads?limit=200
```

Create a workload:
```http
POST /nerve/v3/workloads
Content-Type: application/json

{
  "name": "temperature-collector",
  "type": "docker",
  "disabled": false
}
```

Delete a workload:
```http
DELETE /nerve/v3/workloads/{workload_id}
```

## Workload versions: list, create, delete

List versions for a workload:
```http
GET /nerve/v3/workloads/{workload_id}/versions
```

Create a workload version:
```http
POST /nerve/v3/workloads/{workload_id}/versions
Content-Type: application/json

{
  "name": "1.0.0",
  "releaseName": "1.0.0",
  "selectors": [],
  "restartPolicy": "always",
  "resources": {},
  "environmentVariables": [],
  "secrets": []
}
```

Delete a workload version:
```http
DELETE /nerve/v3/workloads/{workload_id}/versions/{version_id}
```

## Deploy or undeploy via DNA target

The DNA target represents the desired workload versions on a node. Applying a
new target deploys any new workload/version pairs and undeploys any removed
pairs.

Get current target (YAML):
```http
GET /nerve/dna/{serialNumber}/target
Accept: text/yaml
```

Apply target (YAML):
```http
PUT /nerve/dna/{serialNumber}/target
Content-Type: text/yaml

schema_version: 1
workloads:
  - name: temperature-collector
    version: 1.0.0
  - name: vibration-monitor
    version: 2.1.3
```

Rules enforced by the simulator:
- The node must exist and not be OFFLINE.
- Each workload/version pair must exist in the workload catalog.
- `workloads` must be a list of objects with `name` and `version`.

To undeploy a workload version, remove it from the `workloads` list and reapply
the target.



