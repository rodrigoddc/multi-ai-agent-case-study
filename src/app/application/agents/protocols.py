"""Protocol contracts for application AI agents."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AIAgent(Protocol):
    """Application contract for an executable AI agent."""

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the agent and return LangGraph-compatible state updates.

        Args:
            state: Current application agent state.

        Returns:
            Partial state update produced by the agent.
        """
        ...
