#SKILL.md

This is about how to achieve intent-based management of FILL's machine analytics system. FILL manages a number of machine tools, on each of which can be deployed with several workloads (with a specific version) for data anlytics. 

## Input

The user often provide "intents" about what they want to achieve for a machine. A Serial Numer of the target machine is mandatory. Ask the user if this is missing. They will normally not direcly mentioning which workloads, and this requires "system reasoning" step.

## Step 1: system reasoning (optional)

Based on user intent, an agent can do reasoning based on the knowledge graph of the whole FILL system to decide which workloads should be deployed on the target machine. There is a dedicated skill  (fill-system-reasoning) about this. The output of this step is a list of workloads. Note that this skill only allows to get the workloads, without specific versions. Always ask the agent to only provide the workload (container) names, without any explanation or any other addition information.

## Step 2: API invocation

If the users provided specific workloads, or such workloads are received from a reasoning agent, an agent can call the FILL's NERVE api to deploy the workloads. There is skill ("fill-api-invocation") describes how to call the APIs. The same API can be used to check what machiens are there, the status of the machines, the current deployment, and the available workloads. 

When you call the API invocation agent for the first time, tell it the host of the endpoint. (if you don't know, ask the user)