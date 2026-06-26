import asyncio
import uuid
from types import SimpleNamespace
from typing import AsyncGenerator
from unittest.mock import AsyncMock

from src.app.application.services.chat_service import (
    ChatServiceTimeoutError,
    LLMProviderUnavailableError,
)

import pytest
from httpx import ASGITransport, AsyncClient
from sse_starlette.event import ServerSentEvent

from src.app.application.dependencies import (
    get_chat_service,
    get_insight_summary_service,
    get_sse_service,
)
from src.app.bootstrap.container import ApplicationContainer
from src.app.infrastructure.config import settings
from src.app.main import create_app


class MockChatService:
    def __init__(self):
        self.called = False
        self.last_args = None
        self.process_chat_mock = AsyncMock(side_effect=self._process_chat)

    async def process_chat(
        self,
        message: str,
        thread_id: str | None = None,
        user_id: str = "anonymous",
        session_id: str | None = None,
        tracing_config: dict | None = None,
    ):
        try:
            return await self.process_chat_mock(
                message=message,
                thread_id=thread_id,
                user_id=user_id,
                session_id=session_id,
                tracing_config=tracing_config,
            )
        except Exception as e:
            if isinstance(e, TimeoutError) or "timeout" in str(e).lower():
                raise ChatServiceTimeoutError(f"LLM request timed out: {e}") from e
            raise

    async def _process_chat(
        self,
        message: str,
        thread_id: str | None = None,
        user_id: str = "anonymous",
        session_id: str | None = None,
        tracing_config: dict | None = None,
    ):
        self.called = True
        self.last_args = (message, thread_id, user_id, session_id)
        return {
            "final_answer": "**Top performers**\n\n- **Alpine Retreat** is rising\n- Skyline Plaza is strong",
            "thread_id": thread_id or "mock-thread",
            "reasoning_trace": "mock-trace",
        }


class MockSSEService:
    def __init__(self, messages):
        self.messages = messages
        self.last_args = None

    async def stream_chat(
        self,
        message: str,
        user_id: str = "anonymous",
        thread_id: str = "",
        session_id: str | None = None,
        tracing_config: dict | None = None,
        message_id: str | None = None,
        target_id: str = "chat-messages",
        thread_input_id: str = "thread-id",
        display_name: str | None = None,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        self.last_args = (
            message,
            thread_id,
            user_id,
            session_id,
            message_id,
            target_id,
            thread_input_id,
        )
        for text in self.messages:
            yield ServerSentEvent(
                event="ChatUpdate", data=f'<span class="text-sm">{text}</span>'
            )
            await asyncio.sleep(0)
        yield ServerSentEvent(event="done", data="")


class MockTracingService:
    def __init__(self):
        self.calls = []

    def build_config(
        self,
        user_id: str,
        session_id: str | None,
        thread_id: str | None,
        trace_id: str | None = None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "thread_id": thread_id,
                "trace_id": trace_id,
            }
        )
        return {"metadata": self.calls[-1]}


class MockSummaryService:
    async def get_summary(self):
        return {
            "hotel_count": 10,
            "average_occupancy_rate": 78.07,
            "average_revpar": 156.63,
            "average_sentiment": 78.8,
        }


@pytest.fixture
async def client():
    mock_chat = MockChatService()
    mock_sse = MockSSEService(
        [
            "Routing your question",
            "Analyzing hotel performance data",
            "Formatting the final answer",
        ]
    )
    mock_summary = MockSummaryService()
    mock_tracing = MockTracingService()

    test_app = create_app(settings.APP_ENV)

    async def override_chat_service():
        return mock_chat

    async def override_sse_service():
        return mock_sse

    async def override_summary_service():
        return mock_summary

    test_app.dependency_overrides[get_chat_service] = override_chat_service
    test_app.dependency_overrides[get_sse_service] = override_sse_service
    test_app.dependency_overrides[get_insight_summary_service] = (
        override_summary_service
    )
    test_app.state.container = ApplicationContainer(
        settings=SimpleNamespace(environment="test"),
        graph=object(),
        repository=object(),
        llm=object(),
        chat_service=object(),
        sse_chat_service=object(),
        hotel_query_service=object(),
        insight_summary_service=object(),
        tracing_service=mock_tracing,
    )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c, mock_chat, mock_sse, mock_tracing

    test_app.dependency_overrides.clear()


async def test_post_chat_returns_stable_run_stepper_container(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.post(
        "/insights/chat", data={"message": "Hello testing", "thread_id": "t1"}
    )

    assert resp.status_code == 200
    assert mock_chat.called is False
    assert "Hello testing" in resp.text
    assert "chat-response-card" in resp.text
    assert "chat-progress-summary" in resp.text
    assert "chat-run-steps" in resp.text
    assert "chat-final-answer-receiver" not in resp.text
    assert "chat-final-answer" in resp.text
    assert "chat-workflow-details" in resp.text
    assert "chat-workflow-summary" in resp.text
    assert "chat-workflow-content" in resp.text
    assert 'sse-connect="/insights/chat/stream' in resp.text
    assert 'sse-swap="ChatStatus"' in resp.text
    assert 'sse-swap="ChatCompletedStep"' in resp.text
    assert 'sse-swap="ChatActiveStep"' in resp.text
    assert 'sse-swap="ChatFinal"' in resp.text
    assert 'sse-close="done"' in resp.text
    assert "AI agent workflow" in resp.text
    assert "Top performers" not in resp.text
    assert "data-stream-url" not in resp.text


async def test_get_chat_response_returns_server_rendered_ai_response(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get(
        "/insights/chat/response",
        params={"message": "Hello testing", "thread_id": "t1"},
    )

    assert resp.status_code == 200
    assert mock_chat.called is True
    assert "<strong>Top performers</strong>" in resp.text
    assert "Alpine Retreat" in resp.text
    assert "**" not in resp.text
    assert "sse-connect" not in resp.text
    assert "thread-id" in resp.text
    assert "hx-swap-oob" in resp.text


async def test_get_chat_stream_streams_events(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get(
        "/insights/chat/stream?thread_id=t1&message_id=m1&query=Hello",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 200
    text = resp.text
    assert "data:" in text
    assert "Routing your question" in text
    assert "Analyzing hotel performance data" in text


async def test_summary_fragment_renders_metric_cards_without_client_js(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get("/insights/summary/fragment")

    assert resp.status_code == 200
    assert "Total Hotels" in resp.text
    assert "10" in resp.text
    assert "Avg Occupancy" in resp.text
    assert "78.1%" in resp.text
    assert "7807.0%" not in resp.text


async def test_query_fragment_renders_clean_html_without_markdown(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get("/insights/query/fragment?query=Show%20top%20hotels")

    assert resp.status_code == 200
    assert "Top performers" in resp.text
    assert "Alpine Retreat" in resp.text
    assert "**" not in resp.text
    assert "<li" in resp.text


async def test_query_fragment_returns_visible_error_when_llm_times_out(client):
    c, mock_chat, mock_sse, mock_tracing = client
    mock_chat.process_chat_mock.side_effect = TimeoutError("llm timed out")

    resp = await c.get("/insights/query/fragment?query=Show%20top%20hotels")

    assert resp.status_code == 200
    assert "Insight temporarily unavailable" in resp.text
    assert (
        "The model provider did not answer before the request timed out." in resp.text
    )
    assert "Try again" in resp.text


async def test_query_fragment_returns_visible_error_when_llamacpp_is_down(client):
    c, mock_chat, mock_sse, mock_tracing = client
    mock_chat.process_chat_mock.side_effect = LLMProviderUnavailableError(
        "Local llama.cpp server is unavailable. Start the llama.cpp service and try again."
    )

    resp = await c.get("/insights/query/fragment?query=Show%20top%20hotels")

    assert resp.status_code == 200
    assert "Insight temporarily unavailable" in resp.text
    assert "Local llama.cpp server is unavailable" in resp.text
    assert "Traceback" not in resp.text


async def test_chat_response_returns_visible_error_when_llamacpp_is_down(client):
    c, mock_chat, mock_sse, mock_tracing = client
    mock_chat.process_chat_mock.side_effect = LLMProviderUnavailableError(
        "Local llama.cpp server is unavailable. Start the llama.cpp service and try again."
    )

    resp = await c.get(
        "/insights/chat/response",
        params={"message": "Hello testing", "thread_id": "t1"},
    )

    assert resp.status_code == 503
    assert "Local llama.cpp server is unavailable" in resp.text
    assert "Traceback" not in resp.text


async def test_report_loads_only_summary_and_defers_ai_queries_to_refresh_buttons(
    client,
):
    c, mock_chat, mock_sse, mock_tracing = client

    report = await c.get("/insights/report")
    summary = await c.get("/insights/summary/fragment")

    assert report.status_code == 200
    assert summary.status_code == 200
    assert mock_chat.process_chat_mock.await_count == 0
    assert 'hx-trigger="intersect once"' in report.text
    assert "query/fragment" in report.text
    assert "Generate narrative" in report.text
    assert "Analyze top performers" in report.text
    assert "Analyze risks" in report.text


async def test_query_fragment_generates_unique_thread_and_session_ids_per_request(
    client,
):
    c, mock_chat, mock_sse, mock_tracing = client

    first = await c.get("/insights/query/fragment?query=Show%20top%20hotels")
    first_args = mock_chat.last_args
    second = await c.get("/insights/query/fragment?query=Show%20top%20hotels")
    second_args = mock_chat.last_args

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_args[1] != second_args[1]
    assert first_args[3] != second_args[3]


async def test_chat_post_without_thread_id_generates_unique_thread_ids(client):
    c, mock_chat, mock_sse, mock_tracing = client

    first = await c.post("/insights/chat", data={"message": "Hello testing"})
    second = await c.post("/insights/chat", data={"message": "Hello testing"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert 'value=""' in first.text
    assert first.text != second.text


def assert_uuid8_hex(value: str | None):
    assert value is not None
    parsed = uuid.UUID(value)
    assert parsed.version == 8
    assert parsed.hex == value.strip()


async def test_query_endpoint_generates_all_missing_request_identity_ids(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get("/insights/query", params={"query": "Show top hotels"})

    assert resp.status_code == 200
    message, thread_id, user_id, session_id = mock_chat.last_args
    trace_call = mock_tracing.calls[-1]
    assert message == "Show top hotels"
    assert user_id == "anonymous"
    assert_uuid8_hex(thread_id)
    assert_uuid8_hex(session_id)
    assert_uuid8_hex(trace_call["trace_id"])
    assert trace_call["user_id"] == "anonymous"
    assert trace_call["thread_id"] == thread_id
    assert trace_call["session_id"] == session_id


async def test_chat_response_generates_missing_thread_session_and_trace_ids(client):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get("/insights/chat/response", params={"message": "Hello testing"})

    assert resp.status_code == 200
    message, thread_id, user_id, session_id = mock_chat.last_args
    trace_call = mock_tracing.calls[-1]
    assert message == "Hello testing"
    assert user_id == "anonymous"
    assert_uuid8_hex(thread_id)
    assert_uuid8_hex(session_id)
    assert_uuid8_hex(trace_call["trace_id"])
    assert trace_call["thread_id"] == thread_id
    assert trace_call["session_id"] == session_id


async def test_chat_stream_generates_missing_thread_session_trace_and_message_ids(
    client,
):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get(
        "/insights/chat/stream?query=Hello",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 200
    message, thread_id, user_id, session_id, message_id, target_id, thread_input_id = (
        mock_sse.last_args
    )
    trace_call = mock_tracing.calls[-1]
    assert message == "Hello"
    assert user_id == "anonymous"
    assert_uuid8_hex(thread_id)
    assert_uuid8_hex(session_id)
    assert_uuid8_hex(message_id)
    assert_uuid8_hex(trace_call["trace_id"])
    assert trace_call["thread_id"] == thread_id
    assert trace_call["session_id"] == session_id
    assert target_id == "chat-messages"
    assert thread_input_id == "thread-id"


async def test_identity_headers_are_trimmed_and_blank_user_defaults_to_anonymous(
    client,
):
    c, mock_chat, mock_sse, mock_tracing = client

    resp = await c.get(
        "/insights/query",
        params={"query": "Show top hotels", "thread_id": "  explicit-thread  "},
        headers={"X-User-ID": "   ", "X-Session-ID": "  explicit-session  "},
    )

    assert resp.status_code == 200
    message, thread_id, user_id, session_id = mock_chat.last_args
    assert message == "Show top hotels"
    assert thread_id == "explicit-thread"
    assert user_id == "anonymous"
    assert session_id == "explicit-session"
