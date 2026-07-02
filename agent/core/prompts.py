"""System-prompt builders for the captain and worker agents.

A prompt is assembled from sections:
  1. A shared base (tool usage, fallback behaviour).
  2. A role-specific block (captain vs worker rules).
  3. The folder's SKILL.md content, if loaded.
  4. Environment notes derived from the SKILL.md (compatibility + setup).
  5. The folder overview (one-liner produced by core.fs.list_folder_overview).

Empty sections are skipped. Sections are joined with blank lines so the
LLM can clearly distinguish them.
"""

from core.skills import build_environment_notes


def base_system_prompt() -> str:
    return (
        "You are a command-line agent running in a container with access to a local shell and file system. "
        "Use the provided tools when you need to read/write files, run shell commands, execute Python, or call remote APIs. "
        "If needed information is missing or unclear, ask a concise follow-up question."
    )


def build_captain_prompt(folder_overview: str, folder_skill: str) -> str:
    """Assemble the captain's system prompt.

    The captain coordinates the conversation and may delegate to specialized
    sub-agents via the ``delegate_task`` tool.
    """
    base = base_system_prompt()
    captain_rules = (
        "You are the main coordinator agent named 'captain'. "
        "Use the SKILL.md for your assigned folder below for domain instructions and workflows. "
        "Treat the SKILL.md as binding instructions; follow it exactly and refuse or ask for clarification if a request conflicts. "
        "When the skill is loaded, verify any compatibility requirements and run the setup instructions if needed before proceeding. "
        "If requirements are missing and no setup instructions exist, ask for guidance. "
        "When a task should be specialized split it into subtasks and delegate them via the delegate_task tool. "
        "This tool will create another agent with specified folder."
        "This also applies when you see the need to use a different skill - create a new agent using delegate_task tool, and appoint the folder with that skill."
        "Each sub-agent must be assigned a folder that is the same as yours or a sub-folder under yours."
        "When the user reports a correction or improvement to make to an existing SKILL.md, call the invoke_supervisor tool and pass along the user's instruction instead of modifying the skill yourself."
    )
    sections = [base, captain_rules]
    if folder_skill:
        sections.append("Folder SKILL.md:\n" + folder_skill)
        environment_notes = build_environment_notes(folder_skill)
        if environment_notes:
            sections.append(environment_notes)
    if folder_overview:
        sections.append(folder_overview)
    return "\n\n".join(section for section in sections if section).strip()


def build_worker_prompt(
    folder_path: str,
    skill_content: str,
    agent_name: str,
    folder_overview: str,
) -> str:
    """Assemble a worker sub-agent's system prompt.

    The worker is strictly scoped to a single folder and a single SKILL.md.
    It has no ``delegate_task`` tool (see core.tools).
    """
    base = base_system_prompt()
    worker_rules = (
        f"You are a specialized sub-agent named '{agent_name}'. "
        f"You are strictly limited to the folder '{folder_path}' and must not use or request folders outside it. "
        "Treat the SKILL.md as binding instructions; follow it exactly and refuse or ask for clarification if a request conflicts. "
        "When the skill is loaded, verify any compatibility requirements and run the setup instructions if needed before proceeding. "
        "If requirements are missing and no setup instructions exist, ask for guidance. "
        "If a request is outside this folder, say so plainly."
    )
    sections = [base, worker_rules, f"Folder SKILL.md:\n{skill_content}"]
    environment_notes = build_environment_notes(skill_content)
    if environment_notes:
        sections.append(environment_notes)
    if folder_overview:
        sections.append(folder_overview)
    return "\n\n".join(section for section in sections if section).strip()


def build_supervisor_prompt(
    folder_path: str,
    skill_content: str,
    folder_overview: str,
) -> str:
    """Assemble the supervisor agent's system prompt.

    The supervisor revises other agents' SKILL.md files and has access to
    revise_skill, but not delegation tools.
    """
    base = base_system_prompt()
    supervisor_rules = (
        "You are the supervisor agent. "
        f"Your own instruction folder is '{folder_path}'. "
        "Your job is to improve targeted SKILL.md files when the captain relays a user request. "
        "Only edit skills; do not execute the target skill's domain task. "
        "Never delegate work, never invoke another supervisor, and never inspect the agent roster. "
        "Use revise_skill for every SKILL.md modification. "
        "The revise_skill tool creates a mandatory backup before writing; do not bypass it with file-writing tools. "
        "Rewrite target skills in clear, prescriptive language with explicit constraints and expected behavior. "
        "Keep each revision scoped to the captain's instruction and modify only the targeted SKILL.md."
    )
    sections = [base, supervisor_rules, f"Supervisor SKILL.md:\n{skill_content}"]
    environment_notes = build_environment_notes(skill_content)
    if environment_notes:
        sections.append(environment_notes)
    if folder_overview:
        sections.append(folder_overview)
    return "\n\n".join(section for section in sections if section).strip()
