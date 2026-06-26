from pathlib import Path
from typing import Any, cast

from src.app.application.services.chat_service import LLMProviderUnavailableError
from src.app.application.services.sse_chat_service import SSEChatService


class MockGraph:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def astream(self, initial_state, config, stream_mode=None, version=None):
        self.calls.append(
            {
                "initial_state": initial_state,
                "config": config,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        yield {
            "type": "custom",
            "ns": (),
            "data": {"content": "Gandalf is choosing the path"},
        }
        yield {"type": "custom", "ns": (), "data": {"content": "Loading hotel metrics"}}
        yield {
            "type": "updates",
            "ns": (),
            "data": {"gandalf": {"route_decision": "gandalf"}},
        }
        yield {
            "type": "custom",
            "ns": (),
            "data": {"type": "tool_call", "name": "get_top_hotels"},
        }
        yield (
            {
                "type": "updates",
                "ns": (),
                "data": {"gandalf": {"insights": ["Portfolio metrics analyzed"]}},
            }
        )
        yield {
            "type": "custom",
            "ns": (),
            "data": {"content": "Loading hotel metrics"},
        }
        yield {
            "type": "custom",
            "ns": (),
            "data": {"type": "tool_call", "name": "llm.generate"},
        }
        yield {
            "type": "updates",
            "ns": (),
            "data": {"gandalf": {"compliance_status": {"is_compliant": True}}},
        }
        yield {
            "type": "updates",
            "ns": (),
            "data": {
                "gandalf": {"final_answer": "**Hello** <strong>safe</strong> world"}
            },
        }


class LegacyTupleGraph(MockGraph):
    async def astream(self, initial_state, config, stream_mode=None, version=None):
        self.calls.append(
            {
                "initial_state": initial_state,
                "config": config,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        yield ((), "custom", {"content": "Loading hotel metrics"})
        yield ((), "updates", {"gandalf": {"route_decision": "gandalf"}})


class InterruptPayload:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value


class ProviderUnavailableGraph(MockGraph):
    async def astream(self, initial_state, config, stream_mode=None, version=None):
        self.calls.append(
            {
                "initial_state": initial_state,
                "config": config,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        raise LLMProviderUnavailableError(
            "Local llama.cpp server is unavailable. Start the llama.cpp service and try again."
        )
        yield {}


class ClarificationGraph(MockGraph):
    async def astream(self, initial_state, config, stream_mode=None, version=None):
        self.calls.append(
            {
                "initial_state": initial_state,
                "config": config,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        yield {
            "type": "updates",
            "data": {
                "gandalf": {
                    "final_answer": "Could you specify a time period?",
                    "requires_approval": True,
                    "approval_context": {
                        "question": "Could you specify a time period?"
                    },
                }
            },
        }
        yield {
            "type": "updates",
            "data": {
                "__interrupt__": (
                    InterruptPayload(
                        {
                            "question": "Could you specify a time period?",
                            "options": ["Current portfolio by RevPAR"],
                        }
                    ),
                )
            },
        }


def event_data(event) -> str:
    return cast(str, event.data)


async def test_stream_chat_emits_only_real_custom_activity_and_tool_calls():
    graph = MockGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]

    assert graph.calls[0]["stream_mode"] == ["updates", "custom"]
    assert graph.calls[0]["version"] == "v2"
    assert [event.event for event in events] == [
        "ChatStatus",
        "ChatActiveStep",
        "ChatStatus",
        "ChatCompletedStep",
        "ChatActiveStep",
        "ChatStatus",
        "ChatCompletedStep",
        "ChatActiveStep",
        "ChatStatus",
        "ChatCompletedStep",
        "ChatActiveStep",
        "ChatCompletedStep",
        "ChatActiveStep",
        "ChatStatus",
        "ChatFinal",
        "done",
    ]
    text = "\n".join(event_data(event) for event in events)
    assert text.index("Loading hotel metrics") < text.index(
        "calling tool: get_top_hotels"
    )
    assert text.index("calling tool: get_top_hotels") < text.index(
        "Calling tool: llm.generate"
    )
    assert "Routing your question" not in text
    assert "Analyzing hotel performance data" not in text
    assert "Checking compliance and response quality" not in text
    assert "Formatting the final answer" not in text
    assert text.count("Loading hotel metrics") == 3
    final_answer = event_data(
        next(event for event in events if event.event == "ChatFinal")
    )
    assert "Hello &lt;strong&gt;safe&lt;/strong&gt; world" in final_answer
    assert "chat-final-answer-content" in final_answer
    assert "chat-final-answer-message" not in final_answer
    assert "Completed" not in final_answer
    assert "Show reasoning trace" not in final_answer
    assert "hx-swap-oob" not in final_answer
    assert "**" not in final_answer


async def test_stream_chat_marks_latest_step_running_and_previous_steps_complete():
    graph = MockGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]
    step_events = [
        event
        for event in events
        if event.event in {"ChatCompletedStep", "ChatActiveStep"}
    ]

    first_step = event_data(step_events[0])
    second_step = event_data(step_events[1])

    assert "chat-timeline-item-running" in first_step
    assert "chat-timeline-item-complete" in second_step
    assert "chat-active-step-m1" in first_step
    assert "chat-completed-step-m1-1" in second_step
    assert "hx-swap-oob" not in second_step


async def test_stream_chat_completes_final_active_step_before_answer():
    graph = MockGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]
    final_event_index = next(
        index for index, event in enumerate(events) if event.event == "ChatFinal"
    )
    preceding_events = events[:final_event_index]
    completed_steps = [
        event for event in preceding_events if event.event == "ChatCompletedStep"
    ]
    clear_active_events = [
        event
        for event in preceding_events
        if event.event == "ChatActiveStep" and event_data(event) == ""
    ]
    status_events = [event for event in preceding_events if event.event == "ChatStatus"]

    assert "calling tool: llm.generate" in event_data(completed_steps[-1])
    assert clear_active_events
    assert "Assistant workflow complete" in event_data(status_events[-1])


async def test_stream_chat_groups_activity_by_agent_as_graph_tree():
    graph = MockGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]
    text = "\n".join(event_data(event) for event in events)

    assert "Gandalf agent" in text
    assert "choosing the path" in text
    assert "Elrond agent" in text
    assert "calling tool: get_top_hotels" in text
    assert "chat-agent-graph" in text
    assert text.count("Elrond agent") >= 1


async def test_stream_chat_generates_unique_thread_ids_per_call():
    graph = MockGraph()
    service = SSEChatService(graph=cast(Any, graph))

    first_events = [event async for event in service.stream_chat(message="Hello")]
    second_events = [event async for event in service.stream_chat(message="Hello")]

    first_final = event_data(
        next(event for event in first_events if event.event == "ChatFinal")
    )
    second_final = event_data(
        next(event for event in second_events if event.event == "ChatFinal")
    )
    first_thread = first_final.split('value="')[1].split('"')[0]
    second_thread = second_final.split('value="')[1].split('"')[0]
    assert first_thread
    assert second_thread
    assert first_thread != second_thread


def test_sse_chat_service_does_not_hardcode_html_fragments_or_synthetic_node_steps():
    source = Path("src/app/application/services/sse_chat_service.py").read_text()

    assert "<div" not in source
    assert "<li" not in source
    assert "html.escape" not in source
    assert "TemplateResponse" not in source
    assert "_build_phase_events" not in source
    assert "_NODE_STATUS" not in source


async def test_stream_chat_still_accepts_legacy_tuple_stream_parts():
    graph = LegacyTupleGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [event async for event in service.stream_chat(message="Hello")]

    assert len(events) == 3
    assert events[0].event == "ChatStatus"
    assert events[1].event == "ChatActiveStep"
    assert "Loading hotel metrics" in event_data(events[1])
    assert events[2].event == "done"


async def test_stream_chat_renders_clarification_once_from_interrupt_payload():
    graph = ClarificationGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]

    final_events = [event for event in events if event.event == "ChatFinal"]
    assert len(final_events) == 1
    final = event_data(final_events[0])
    assert final.count("Could you specify a time period?") == 1
    assert "chat-final-answer-clarification" in final
    assert "Current portfolio by RevPAR" in final
    assert 'hx-post="/insights/chat"' in final


async def test_stream_chat_renders_provider_unavailable_as_final_message():
    graph = ProviderUnavailableGraph()
    service = SSEChatService(graph=cast(Any, graph))

    events = [
        event async for event in service.stream_chat(message="Hello", message_id="m1")
    ]

    assert [event.event for event in events] == ["ChatStatus", "ChatFinal", "done"]
    text = "\n".join(event_data(event) for event in events)
    assert "Local llama.cpp server is unavailable" in text
    assert "Traceback" not in text


def test_clarification_options_are_only_extracted_from_explicit_binary_choice():
    service = SSEChatService(graph=cast(Any, ClarificationGraph()))

    assert (
        service._extract_options_from_question(
            "Which hotel or portfolio scope, date interval, and metric should I use?"
        )
        is None
    )
    assert service._extract_options_from_question(
        "Would you like portfolio RevPAR or hotel occupancy?"
    ) == ["portfolio RevPAR", "hotel occupancy"]
