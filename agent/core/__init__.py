"""inSwitch agent core.

Generic multi-agent orchestration engine: a captain coordinator and worker
sub-agents, each bound to a SKILL.md-defined folder, communicating via
OpenAI's Responses API. Domain-specific behaviour lives in skills under
/workspace; this package is the use-case-agnostic core that loads and
dispatches them.

This package is being progressively extracted from the monolithic app.py.
See AGENT.md for the package layout.
"""

__version__ = "0.2.0"