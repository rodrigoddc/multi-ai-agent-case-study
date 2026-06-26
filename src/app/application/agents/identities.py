"""LOTR agent identities for the multi-agent fellowship."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentName(StrEnum):
    """Stable internal identifiers for the LOTR agents."""

    GANDALF = "gandalf"
    ARAGORN = "aragorn"
    SAMWISE = "samwise"
    ELROND = "elrond"
    BILBO = "bilbo"
    FARAMIR = "faramir"
    RADAGAST = "radagast"


@dataclass(frozen=True)
class AgentIdentity:
    """Display metadata for a named AI agent."""

    name: AgentName
    display_name: str
    role: str
    progress_label: str


AGENT_IDENTITIES: dict[AgentName, AgentIdentity] = {
    AgentName.GANDALF: AgentIdentity(
        name=AgentName.GANDALF,
        display_name="Gandalf",
        role="Coordinates the hotel insights fellowship and delegates work.",
        progress_label="Gandalf is choosing the path",
    ),
    AgentName.ARAGORN: AgentIdentity(
        name=AgentName.ARAGORN,
        display_name="Aragorn",
        role="Checks safety, scope, and policy before data access.",
        progress_label="Aragorn is checking safety",
    ),
    AgentName.SAMWISE: AgentIdentity(
        name=AgentName.SAMWISE,
        display_name="Samwise",
        role="Loads and remembers user preferences and context.",
        progress_label="Samwise is gathering context",
    ),
    AgentName.ELROND: AgentIdentity(
        name=AgentName.ELROND,
        display_name="Elrond",
        role="Analyzes read-only hotel portfolio data.",
        progress_label="Elrond is studying the portfolio",
    ),
    AgentName.BILBO: AgentIdentity(
        name=AgentName.BILBO,
        display_name="Bilbo",
        role="Writes the final concise user-facing answer.",
        progress_label="Bilbo is drafting the answer",
    ),
    AgentName.FARAMIR: AgentIdentity(
        name=AgentName.FARAMIR,
        display_name="Faramir",
        role="Reviews final answers for groundedness, quality, and safety.",
        progress_label="Faramir is reviewing the answer",
    ),
    AgentName.RADAGAST: AgentIdentity(
        name=AgentName.RADAGAST,
        display_name="Radagast",
        role="Answers weather and nature-condition questions.",
        progress_label="Radagast is reading the skies",
    ),
}
