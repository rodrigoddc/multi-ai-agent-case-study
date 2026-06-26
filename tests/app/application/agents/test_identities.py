from src.app.application.agents.identities import AGENT_IDENTITIES, AgentName


def test_lotr_agent_identities_are_character_names():
    expected = {
        AgentName.GANDALF: "Gandalf",
        AgentName.ARAGORN: "Aragorn",
        AgentName.SAMWISE: "Samwise",
        AgentName.ELROND: "Elrond",
        AgentName.BILBO: "Bilbo",
        AgentName.FARAMIR: "Faramir",
        AgentName.RADAGAST: "Radagast",
    }

    assert {
        name: identity.display_name for name, identity in AGENT_IDENTITIES.items()
    } == expected


def test_old_technical_names_are_not_display_names():
    forbidden = {
        "Supervisor",
        "Router",
        "Compliance",
        "InsightGenerator",
        "Mike",
        "Clovis",
        "Ditto",
    }

    assert forbidden.isdisjoint(
        {identity.display_name for identity in AGENT_IDENTITIES.values()}
    )
