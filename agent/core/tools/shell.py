"""Shell and Python execution tools."""

import subprocess
import sys
from typing import Any, Dict

from core.config import WORKSPACE_DIR
from core.tools import tool, ToolContext


@tool(
    name="run_shell",
    description=(
        "Run a shell command in the container and return stdout, stderr, "
        "and exit code. Defaults to the agent's folder if cwd is not "
        "provided."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": (
                    "Working directory. Defaults to the agent's folder "
                    "under /workspace."
                ),
            },
        },
        "required": ["command"],
    },
)
def run_shell(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    # The captain/worker may pass cwd as the agent's resolved folder; if
    # absent we fall back to the workspace root to match the original.
    command = args.get("command", "")
    workdir = args.get("cwd") or WORKSPACE_DIR
    result = subprocess.run(
        command,
        shell=True,
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }


@tool(
    name="run_python",
    description=(
        "Execute a Python code snippet and return stdout, stderr, and "
        "exit code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to run."},
        },
        "required": ["code"],
    },
)
def run_python(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    code = args.get("code", "")
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=WORKSPACE_DIR,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }