"""Tests proving LOTR agents use AgentConfig instead of constructor defaults."""

from pathlib import Path


AGENT_FILES = (
    "aragorn.py",
    "bilbo.py",
    "elrond.py",
    "faramir.py",
    "radagast.py",
    "samwise.py",
)


def test_lotr_agent_constructors_do_not_pass_hardcoded_prompt_or_temperature():
    agents_dir = Path("src/app/application/agents")

    for filename in AGENT_FILES:
        source = (agents_dir / filename).read_text()

        assert "system_prompt=" not in source
        assert "temperature=" not in source


def test_lotr_agent_modules_do_not_define_prompt_constants_or_inline_personas():
    agents_dir = Path("src/app/application/agents")

    for filename in (*AGENT_FILES, "gandalf.py"):
        source = (agents_dir / filename).read_text()

        assert "SYSTEM_PROMPT" not in source
        assert "DEFAULT_" not in source
        assert "TOOL_PLAN_PROMPT" not in source
        assert "TOOL_SELECTION_PROMPT" not in source
        assert "You are " not in source
        assert "Return only JSON" not in source
