---
name: gate
description: Operate the GATE smart city platform — check system status, answer general questions about the platform, and coordinate service lifecycle tasks (deploy, upgrade, configure, delete) via Helm. Use when the user asks about the GATE smart city system, its services, or wants to manage smart city workloads.
---

# GATE Smart City System

## Overview

This skill covers general operation of the smart city platform built by GATE. It handles two broad categories of requests:

1. **Informational** — answering questions about the platform, its architecture, available services, and current system status.
2. **Service lifecycle** — deploying, upgrading, configuring, or deleting smart city services. These operations are carried out through Helm and must be delegated to the `helm-deploy` sub-skill.

## Informational Requests

Use available tools (shell, HTTP) to collect and report:

- **System status**: overall health of the cluster, running services, recent events or alerts.
- **Service inventory**: list of deployed smart city services, their versions, and namespaces.
- **General platform questions**: architecture, supported service types, configuration patterns.

When answering general questions, be concise and accurate. If live data is needed, gather it first before replying.

## Service Lifecycle Requests

Requests that involve deploying, deleting, upgrading, or configuring a smart city service must be routed to the `helm-deploy` sub-skill under the `helm-deploy/` folder.

Typical trigger phrases:
- "deploy the traffic-monitor service"
- "upgrade air-quality to version 2.1"
- "remove the parking-sensor workload"
- "change the replica count for lighting-control"

When delegating:
1. Confirm the target service name and, if relevant, the target version or configuration values.
2. Pass a clear task description to the `helm-deploy` agent.
3. Report the outcome back to the user in plain language.

## Information to Collect Upfront

Before taking any action, ensure you have:
- The Kubernetes cluster context or API endpoint (ask the user if unknown).
- The target namespace (default: `smart-city`, but confirm if the user implies otherwise).

## Error Handling

- If a service name is ambiguous, list candidates and ask the user to confirm.
- If the cluster is unreachable, report the error clearly and suggest checking connectivity or credentials.
- If a lifecycle request is outside the scope of `helm-deploy`, say so and ask for clarification.
