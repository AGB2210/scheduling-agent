"""The versions of the agent that are compared with each other."""

from dataclasses import dataclass

from schedagent.agent import SOLVER_PROMPT, SYSTEM_PROMPT
from schedagent.tools import PLAIN_TOOLS, SOLVER_TOOLS, Tool


@dataclass(frozen=True)
class Version:
    """One way of setting the agent up: its tools and its instructions."""

    name: str
    tools: dict[str, Tool]
    system_prompt: str


# Reads calendars with get_busy and works out a time itself.
PLAIN = Version("plain", PLAIN_TOOLS, SYSTEM_PROMPT)
# States the rules to find_slots and lets the solver work out the times.
SOLVER = Version("solver", SOLVER_TOOLS, SOLVER_PROMPT)

VERSIONS = {version.name: version for version in (PLAIN, SOLVER)}
