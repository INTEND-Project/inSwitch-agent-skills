# The Supervisor Agent

Technical documentation for the skill-supervision feature of the inSwitch
multi-agent core.

This document describes how the supervisor works, why it is built the way it
is, and how it integrates with the existing agent runtime. It is written for a
developer who needs to understand, operate, or extend the feature. It reflects
the implementation in `core/tools/supervision.py` and `core/prompts.py`.

---

## 1. What the supervisor is

The supervisor is a third kind of agent, alongside the captain and the workers.
Its single responsibility is to revise other agents' `SKILL.md` files at the
request of the user, relayed through the captain. It does not perform any domain
task itself: it never deploys a workload, never queries the NERVE API, never
reasons about zones. It edits skills, and nothing else.

The motivation is the central thesis of the framework. A skill is a prompt: an
agent's behaviour is governed by its `SKILL.md`, loaded as context. Adapting an
agent to a new requirement therefore means rewriting that Markdown, not changing
code. The supervisor turns this from a manual, out-of-band file edit into an
in-band capability: the user describes the change they want in plain language,
and the change is applied to the live skill, with a safety backup, while the
system keeps running.

A concrete example from the FILL use case. A deployment agent was returning the
full raw JSON of every NERVE API response in the chat, which is unreadable. The
fix was not a code change. The user asked, in conversation, for the agent to
summarise outcomes in one or two sentences instead. The captain relayed this to
the supervisor, which rewrote the deployment skill to add an output-formatting
rule. No file was opened by hand, no service was restarted, and the change took
effect on the next turn.

---

## 2. Where the supervisor lives

The supervisor differs from a worker in one structural way that drives most of
its design: its instruction folder lives outside the workspace.

Workers are bound to folders under `/workspace`, the bind-mounted directory that
holds the domain skills (the FILL skills, the GATE skills). The supervisor is
bound instead to `SUPERVISOR_DIR`, which defaults to `/agent/supervisor`. This
path is inside the agent image, not the mounted workspace. The supervisor's own
`SKILL.md` is baked into the image at build time (via the Dockerfile `COPY`),
because it is part of the core engine and is the same for every use case. It is
not domain-specific and must not be editable from a use case.

This separation matters because it forbids a category of mistakes. The
supervisor edits domain skills under `/workspace`; its own instructions sit
apart under `/agent/supervisor`. The two never overlap, so the supervisor cannot
accidentally rewrite itself, and a domain deployment cannot tamper with the
supervisor's rules.

`SUPERVISOR_DIR` is added to `ALLOWED_ROOTS` in `core/config.py`, so the path
guard that protects all file access accepts it as a legitimate root.

---

## 3. The three tools

The feature is implemented as three tools in `core/tools/supervision.py`. Each
is registered through the same `@tool` decorator that every other tool in the
system uses, so the supervisor's capabilities appear in the registry exactly
like `delegate_task` or the shell tools.

### read_skill

Reads the current `SKILL.md` of a folder under `/workspace` and returns its
content. The folder path is given relative to `/workspace`. This is the
supervisor's only way to see a skill before rewriting it. It exists so the
supervisor can make an informed revision: it reads the existing skill, then
produces a complete replacement that preserves what should be kept and changes
only what the instruction asks for. The tool is read-only and carries the
`supervisor_allowed` flag so the supervisor can call it.

### revise_skill

The core of the feature. It replaces a target `SKILL.md` with new content, after
taking a mandatory backup. The order of operations is deliberate and is the main
safety property of the whole feature:

1. **Resolve and validate the path.** The folder path is normalised and resolved
   to an absolute path, and the resulting `SKILL.md` location is checked to be
   strictly under `/workspace`. Anything outside is rejected with an error. This
   confines every revision to domain skills and blocks any attempt to write
   elsewhere in the container.

2. **Read the previous content.** The current file is read and kept, both to
   return it to the caller and to ensure the file exists before anything is
   written.

3. **Back up before writing.** The existing `SKILL.md` is copied to
   `<folder>/.skill_backups/SKILL.<timestamp>.md`, where the timestamp is a UTC
   instant down to the microsecond. If this copy fails for any reason, the
   function aborts immediately and returns an error **without touching the
   original file**. There is no path in which the live skill is modified while a
   backup is missing. This is the guarantee that a revision is always
   recoverable.

4. **Write the new content.** Only now is the new content written to the
   `SKILL.md`.

5. **Invalidate caches** (see section 4).

6. **Record the event.** A `skill_revised` event is emitted with the target
   folder, the change summary, and the backup path, so the revision is visible
   in the observability layer.

The function returns a status, the path written, the backup path, the previous
content, and the number of agents whose cache was invalidated.

`revise_skill` is both `captain_only` and `supervisor_allowed`. In practice it is
the supervisor that calls it, but the flags mean the tool is filtered out of an
ordinary worker's toolset.

### invoke_supervisor

The routing tool. It is how the captain hands a skill-change request to the
supervisor. It is `captain_only`: a worker cannot summon the supervisor, and the
supervisor cannot summon another supervisor.

Its behaviour mirrors the existing `delegate_task` tool, with one deliberate
difference. Like `delegate_task`, it creates or reuses an `AgentState` for the
supervisor, loads its `SKILL.md` if not already cached, runs one turn through the
shared runner, and wraps that turn in an `agent.turn` span so the trace tree
shows the captain to supervisor hierarchy. Inbound and outbound messages are
logged as `agent_message` events, exactly as for a normal delegation.

The deliberate difference is the scoping constraint. `delegate_task` enforces
`is_within_parent`: a worker's folder must be the same as, or a sub-folder of,
the captain's folder. The supervisor folder (`/agent/supervisor`) is not under
the captain's workspace folder, so that check would reject it. `invoke_supervisor`
therefore does not apply `is_within_parent` at all. This is intentional and is
the reason a separate routing tool exists rather than reusing `delegate_task`.
The supervisor is bound to `SUPERVISOR_DIR` directly, and if an existing
supervisor state is found pointing elsewhere, its folder is reset to
`SUPERVISOR_DIR` and its caches cleared.

---

## 4. The critical step: cache and response-chain invalidation

Writing the new file is not enough to change an agent's behaviour. This is the
subtlest part of the feature, and the part most likely to fail silently if done
incompletely.

Each agent's state caches two things that can hold a stale skill:

- **`folder_skill`**, the `SKILL.md` content kept in memory so it is not re-read
  on every turn. If only the file on disk changes, an agent that already has the
  old content cached will keep using it.

- **`last_response_id`**, the OpenAI response id from the agent's previous turn.
  The runtime passes it to the next `responses.create` call so the API chains
  context without re-sending the transcript. The problem is that the old skill
  is part of that chained context. Even after `folder_skill` is cleared and the
  new skill is reloaded, the previous response in the chain still carries the old
  instructions, and the model can keep following them.

So `revise_skill` performs a two-level invalidation. After the file is written,
it iterates over every agent in the roster and, for each agent whose normalised
folder path matches the revised folder, it sets `folder_skill = None`,
`skill_name = None`, and `last_response_id = None`. The first two force the new
skill to be reloaded on the next turn. The third breaks the response chain so the
old skill cannot persist implicitly through the OpenAI `previous_response_id`
mechanism.

The folder comparison uses the same path normalisation as the rest of the code,
so an agent registered as `fill-api-invocation` and a revision targeting that
same folder are matched correctly regardless of superficial path differences.

This invalidation is the difference between a revision that appears to work and
one that actually changes behaviour. It was validated directly: revising a
deployment skill to prefer the smallest version number, then the largest, on the
same workload, produced the two opposite behaviours in the same session, with no
code change between them. That only works if both cache levels are cleared on
each revision.

A boundary case worth noting: if no worker bound to the target folder has been
launched yet, the loop finds nothing to invalidate and reports zero invalidated
agents. This is correct. The worker will be created fresh on its next turn and
will read the new skill from disk anyway. Invalidation only has work to do when a
matching agent is already live in memory.

---

## 5. How a revision flows end to end

The path of a single skill change, from the user's message to the changed
behaviour, runs as follows.

The user tells the captain, in plain language, what they want changed about an
existing skill. The captain's prompt instructs it that when the user reports a
correction or improvement to an existing `SKILL.md`, it must call
`invoke_supervisor` and pass the instruction along, rather than editing the skill
itself. The captain does so.

`invoke_supervisor` instantiates or reuses the supervisor, loads its `SKILL.md`,
and runs one supervisor turn inside an `agent.turn` span. Within that turn the
supervisor, following its own prompt, reads the target skill with `read_skill`,
composes a complete rewritten version, and calls `revise_skill` with the target
folder and the new content. `revise_skill` validates the path, backs up the old
file, writes the new one, invalidates any matching live agent, and emits a
`skill_revised` event. Control returns up through the captain to the user.

On the next turn that touches the revised skill, the worker bound to that folder
reloads the new content (its cache having been cleared) and behaves according to
the new instructions.

```
user ──(plain-language change request)──▶ captain
                                            │
                                            │ invoke_supervisor(instruction)
                                            ▼
                                        supervisor  ◀── bound to /agent/supervisor
                                            │
                                  read_skill(folder under /workspace)
                                            │
                                  revise_skill(folder, new_content, summary)
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                   backup old file    write new file    invalidate caches
                   (.skill_backups)    (SKILL.md)        (folder_skill +
                                                          last_response_id)
                                            │
                                   log_event("skill_revised")
```

---

## 6. The supervisor's own instructions

The supervisor's behaviour is shaped by its system prompt, built in
`build_supervisor_prompt` in `core/prompts.py`. The prompt establishes a small
set of hard rules that match the structural constraints described above:

- The supervisor edits skills and does not execute any target skill's domain
  task.
- It never delegates work, never invokes another supervisor, and never inspects
  the agent roster. It has no reason to see other agents and is told not to.
- Every modification goes through `revise_skill`. The prompt explicitly forbids
  bypassing the mandatory backup by using generic file-writing tools.
- Revisions are written in clear, prescriptive language with explicit
  constraints and expected behaviour, and each revision stays scoped to the
  captain's instruction, modifying only the targeted `SKILL.md`.

These prompt rules and the code-level guards reinforce each other. The prompt
tells the supervisor to use `revise_skill` and only `revise_skill`; the toolset
it is given makes the delegation tools unavailable in the first place; and
`revise_skill` itself enforces the backup and the `/workspace` boundary
regardless of what the prompt says. Behaviour is constrained at both the
instruction level and the mechanism level.

---

## 7. Toolset restriction

A worker, the captain, and the supervisor see different sets of tools. The
distinction is carried by two flags on each registered tool: `captain_only` and
`supervisor_allowed`.

The intent is precise. The supervisor must see `read_skill` and `revise_skill`,
so it can read and rewrite skills. It must not see `delegate_task`,
`invoke_supervisor`, or `list_agents`, so it cannot spawn workers, summon another
supervisor, or enumerate the roster. The deployment and domain tools are
likewise out of scope: the supervisor edits instructions, it does not act on the
world.

This restriction is what keeps the supervisor honest. Its job is narrow by
construction, not merely by instruction. Even if its prompt were somehow
misread, the tools required to step outside its role are not in its hands.

The filtering is enforced in the tool registry. Each registered tool carries two
booleans, `captain_only` and `supervisor_allowed`, and `get_schemas` selects the
tool list per role from them. The captain is built with the full list. A worker
is built with the captain-only tools filtered out. The supervisor is built with a
dedicated branch that returns only the tools explicitly marked
`supervisor_allowed`, which are exactly `read_skill` and `revise_skill`. The
delegation tools, the shell, and the file tools are therefore absent from the
supervisor's schema list, not merely discouraged by its prompt. The guarantee is
positive: the supervisor sees an allow-list of two tools, rather than the full
list minus a few.

---

## 8. Observability

Every supervisor action is visible in the tracing layer, which is what makes the
feature auditable rather than a black box.

A supervisor turn produces an `agent.turn` span carrying
`agent.role = "supervisor"` and `agent.folder = /agent/supervisor`, nested under
the captain's request span through the same contextvar mechanism that all spans
use. Inside that turn, the `read_skill` and `revise_skill` calls appear as their
own tool spans. A successful revision emits a `skill_revised` event recording the
target folder, the change summary, and the backup path. Agent creation and the
inbound and outbound messages are logged as `agent_created` and `agent_message`
events, exactly as for ordinary delegation.

In the dashboard, supervisor spans and `skill_revised` events are given a colour
distinct from the captain and the workers, so an intervention on the skills
stands out at a glance in the trace list and the waterfall.

This visibility is not cosmetic. Because a revision rewrites a prompt in natural
language, its effects are not always fully predictable from the instruction
alone, and the trace plus the file system are the means by which an unexpected
effect is caught. A revision that an agent reports as done is not proof that the
file changed: the authoritative signals are the `skill_revised` event, the
presence of a fresh backup on disk, and the changed file content, not the
agent's own summary.

---

## 9. Backups and recovery

Every revision leaves a timestamped copy of the previous skill in a
`.skill_backups/` directory next to the `SKILL.md`. Over a series of revisions,
this directory becomes a complete, ordered history of how a skill evolved.

These backups are runtime artifacts, not source. They are created by the running
system, are specific to the instance and session that produced them, and have the
same status as the trace database or log files. They should be excluded from
version control. Git already serves as the canonical history of skills authored
by hand; `.skill_backups/` is a separate, operational safety net for skills
rewritten live by the supervisor.

Recovery is deliberately manual. The supervisor has no notion of rollback. To
restore a previous version, an operator copies the chosen backup back over the
`SKILL.md` by hand. Asking the supervisor to undo a revision would be the wrong
mechanism: it would rewrite the file again, create a further backup of the
current content, and risk reconstructing the old version from memory rather than
restoring it faithfully. Backup is automatic; restoration is not.

A consequence to keep in mind: restoring a backup by hand does not clear any live
agent's cache, since only `revise_skill` performs invalidation. If a worker bound
to the restored skill is already in memory, it must be allowed to reload, for
instance by restarting the session, for the restoration to take effect.

---

## 10. Known limitations and perspectives

Several characteristics of the current implementation are worth recording, both
as operational caveats and as directions for future work.

**Whole-file rewrite.** A revision replaces the entire `SKILL.md`, it does not
apply a targeted diff. This is robust on Markdown and avoids fragile partial
edits, but it means the supervisor reconstructs the whole file each time, and a
rewrite can incidentally alter formatting or wording that the instruction did not
mention. In practice, revisions have been observed to drop Markdown code fences
or to enrich a rule beyond what was asked. The mechanism is sound; the cost is
that the agent does more than the minimum, and only inspection reveals it.

**Emergent side effects of natural-language revision.** Because a skill is a
prompt, an ambiguous phrase in a revised skill can induce behaviour nobody
intended. A documented case: a formatting rule said the full JSON "remains
available in logs", and the agent interpreted this as an instruction to produce
log files itself, writing JSON dumps to disk. The phrase was a statement of fact
about the automatic tracing, not a request to write files. The fix was a further
revision making the prohibition explicit.

This case also exposes a mechanism-level point. The generic file tools
(`read_file`, `write_file`, `list_dir`) carry neither `captain_only` nor
`supervisor_allowed`, so they are part of every ordinary worker's toolset by
default. They resolve relative paths against the calling agent's own folder.
A worker that decides to write a file therefore can, and a relative path such as
`fill-api-invocation/logs.json` resolves under that worker's own folder, which is
how the unintended `fill-api-invocation/fill-api-invocation/` nesting appeared.
Forbidding the behaviour in the prompt worked, but it is a soft guarantee: the
hard fix would be to remove `write_file` from a worker's toolset when the use case
does not need it. The general lesson is that revising prompts produces effects
that are best caught by systematic inspection of the trace and the file system,
and that hard guarantees are better enforced by the mechanism (the tools an agent
is given, the `/workspace` boundary, the mandatory backup) than by wording in a
prompt.

**No rollback capability.** As described in section 9, restoration is manual by
design. An automatic, safe rollback through the supervisor is a possible future
addition, but it would need a real restore primitive, not a re-revision.

**Manual cache coherence on manual restore.** Hand-restoring a backup bypasses
the invalidation that `revise_skill` performs, so a live agent may keep a stale
skill until the session is restarted. A restore primitive, if added, should
perform the same two-level invalidation.

These points are not defects to be hidden. They are the natural consequences of
making prompts editable at runtime, and the observability layer exists precisely
so that their effects are visible and correctable.
