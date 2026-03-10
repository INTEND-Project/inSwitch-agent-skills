---
name: gate
description: Operate the GATE smart city platform — check system status, answer general questions about the platform, and coordinate service lifecycle tasks (deploy, upgrade, configure, delete) via Helm. Use when the user asks about the GATE smart city system, its services, or wants to manage smart city workloads.
---

# GATE Smart City System

## Overview

This skill covers general operation of the smart city platform built by GATE. It handles the following broad categories of requests:

1. **Smart services information and deployment**  — answering questions about the platform, its architecture, available services, and current system status; deploying, upgrading, configuring, or deleting smart city services. These operations are carried out through Helm and must be delegated to the `helm-deploy` sub-skill.


## Smart services information and deployment

Requests that involve deploying, deleting, upgrading, or configuring a smart city service, and also querying about what services are available, etc., must be delegated to a specific agent loaded with the `helm-deploy` sub-skill under the `helm-deploy/` folder.

Typical trigger phrases:
- "deploy the traffic-monitor service"
- "upgrade air-quality to version 2.1"
- "remove the parking-sensor workload"
- "change the replica count for lighting-control"
- "what services are available"
- "what's the dependency fo services"

When delegating:

1. Pass a simple and clear task description to the `helm-deploy` agent.
2. Report the outcome back to the user in plain language.

## Information to Collect Upfront

Before taking any action, ensure you have:
- The Kubernetes cluster context or API endpoint (optional. only needed if deployment is involved. ask the user if unknown).

## Error Handling

- If a service name is ambiguous, list candidates and ask the user to confirm.
- If the cluster is unreachable, report the error clearly and suggest checking connectivity or credentials.
- If a lifecycle request is outside the scope of `helm-deploy`, say so and ask for clarification.
