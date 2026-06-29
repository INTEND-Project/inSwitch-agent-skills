---
name: supervisor
description: Retrospectively revise another agent's SKILL.md file to improve clarity, correctness, and task performance when the captain relays a user request for skill improvement. Use only for editing targeted SKILL.md instructions, not for executing the target skill's domain task.
---

# Supervisor

This skill revises existing agent skills after the captain relays a user request. Improve the targeted `SKILL.md` so future agents can follow it more reliably.

## Input

Expect the captain to provide:

- The path to the targeted `SKILL.md`.
- The user's requested improvement or observed failure.
- Any relevant context from the agent run that exposed the issue.

If the targeted file path is missing or ambiguous, ask the captain for the exact path before making changes.

## Mandatory rules

- Always create a backup of the targeted `SKILL.md` before any modification.
- Only modify the targeted `SKILL.md`. The backup is the only additional file you may create.
- Rewrite the skill in a clear, prescriptive way.
- Never delegate any task.

## Workflow

1. Read the targeted `SKILL.md` completely.
2. Identify the specific instruction gap, ambiguity, contradiction, or missing procedure described by the captain.
3. Create a backup beside the target file before editing.
4. Rewrite the targeted skill so it gives direct instructions, concrete constraints, and expected outputs.
5. Preserve accurate domain knowledge and remove confusing or stale guidance.
6. Keep the revision scoped to the relayed request. Do not broaden the skill beyond what the user asked to improve.
7. Verify that the final file is internally consistent and still names the same skill.

## Writing style

Use imperative, plain language. Prefer short sections, explicit steps, and MUST/DO NOT rules when behavior is mandatory.

Do not add implementation notes, change logs, or commentary about the revision process to the target skill.
