"""Environment-driven configuration.

All runtime configuration is read from environment variables here, with
sensible defaults. Importing this module performs no side effects beyond
reading os.environ.
"""

import os


CODE_DIR: str = os.getenv("AGENT_CODE_DIR", "/agent")
WORKSPACE_DIR: str = os.getenv("AGENT_WORKSPACE_DIR", "/workspace")
LOGS_DIR: str = os.getenv("AGENT_LOGS_DIR", "/logs")
SUPERVISOR_DIR: str = os.getenv("AGENT_SUPERVISOR_DIR", "/agent/supervisor")

MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")

VERBOSE_DEFAULT: bool = os.getenv("AGENT_VERBOSE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MAX_LOG_CHARS: int = int(os.getenv("AGENT_LOG_MAX_CHARS", "2000"))

HTTP_HOST_DEFAULT: str = os.getenv("AGENT_HTTP_HOST", "0.0.0.0")
HTTP_PORT_DEFAULT: int = int(os.getenv("AGENT_HTTP_PORT", "8085"))

# Paths the agent is allowed to read/write. Anything outside these roots is
# rejected by safe_abs_path (see core.fs).
ALLOWED_ROOTS: list[str] = [WORKSPACE_DIR, CODE_DIR, LOGS_DIR, SUPERVISOR_DIR]
