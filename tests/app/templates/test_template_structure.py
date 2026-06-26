from pathlib import Path


TEMPLATE_ROOT = Path("src/app/templates")
STATIC_ROOT = Path("src/app/static")


def test_base_template_is_layout_only_and_uses_static_assets():
    base_template = (TEMPLATE_ROOT / "layouts/base.html").read_text()

    assert "{% include 'partials/header.html' %}" in base_template
    assert "{% block content %}{% endblock %}" in base_template
    assert '<link rel="stylesheet" href="/static/css/app.css">' in base_template
    assert "htmx.org@2.0.10" in base_template
    assert "htmx-ext-sse@2.2.4" in base_template
    assert "/static/js/app.js" not in base_template
    assert "function showSection" not in base_template
    assert "@keyframes" not in base_template

    header_template = (TEMPLATE_ROOT / "partials/header.html").read_text()
    assert "onclick=" not in header_template
    assert 'href="/chat"' in header_template
    assert 'href="/"' in header_template
    assert 'href="/insights/report"' not in header_template


def test_chat_and_report_pages_compose_separate_sections():
    home_template = (TEMPLATE_ROOT / "pages/home.html").read_text()
    chat_template = (TEMPLATE_ROOT / "pages/chat.html").read_text()
    report_template = (TEMPLATE_ROOT / "pages/report.html").read_text()

    assert "{% extends 'layouts/base.html' %}" in home_template
    assert "{% include 'sections/insights.html' %}" in home_template
    assert "{% include 'sections/assistant_panel.html' %}" in home_template
    assert "sections/chat.html" not in home_template

    assert "{% extends 'layouts/base.html' %}" in chat_template
    assert "{% include 'sections/chat.html' %}" in chat_template
    assert "sections/insights.html" not in chat_template

    assert "{% extends 'layouts/base.html' %}" in report_template
    assert "{% include 'sections/insights.html' %}" in report_template
    assert "sections/chat.html" not in report_template


def test_static_assets_hold_non_trivial_css_without_custom_eventsource_client():
    css = (STATIC_ROOT / "css/app.css").read_text()

    assert "@keyframes" in css
    assert "dot-pulse" in css
    assert not (STATIC_ROOT / "js/app.js").exists()


def test_assistant_panel_is_collapsible_and_reuses_chat_endpoints():
    assistant_panel = (TEMPLATE_ROOT / "sections/assistant_panel.html").read_text()

    assert 'id="assistant-panel-toggle"' in assistant_panel
    assert 'for="assistant-panel-toggle"' in assistant_panel
    assert "assistant-panel" in assistant_panel
    assert "assistant-chat-messages" in assistant_panel
    assert "assistant-thread-id" in assistant_panel
    assert "assistant-chat-typing-indicator" in assistant_panel
    assert 'hx-post="/insights/chat"' in assistant_panel
    assert 'hx-target="#assistant-chat-messages"' in assistant_panel
    assert "target_id" in assistant_panel
    assert "thread_input_id" in assistant_panel
    assert "Ask Questions About Your Hotels" not in assistant_panel
    assert "onclick=" not in assistant_panel
    assert "EventSource" not in assistant_panel
    assert "MutationObserver" not in assistant_panel


def test_chat_scroll_uses_htmx_swap_modifiers_without_custom_javascript():
    base_template = (TEMPLATE_ROOT / "layouts/base.html").read_text()
    chat_template = (TEMPLATE_ROOT / "sections/chat.html").read_text()
    chat_request = (TEMPLATE_ROOT / "components" / "chat_request.html").read_text()
    final_answer = (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()

    assert "/static/js/chat-scroll.js" not in base_template
    assert not (STATIC_ROOT / "js/chat-scroll.js").exists()
    assert "scroll:#chat-messages:bottom" in chat_template
    assert "focus-scroll:true" in chat_template
    assert "scroll:#chat-messages:bottom" in chat_request
    assert "focus-scroll:true" in chat_request
    # Final answer now embeds in the response card, no OOB swap to #chat-messages
    assert 'hx-swap-oob="beforeend:#chat-messages"' not in final_answer
    assert "chat-final-answer-message" not in final_answer
    assert "chat-final-answer-content" in final_answer


def test_templates_use_htmx_sse_extension_without_inline_javascript():
    template_text = "\n".join(
        path.read_text()
        for path in TEMPLATE_ROOT.rglob("*.html")
        if path.name != "base.html"
    )

    assert "onclick=" not in template_text
    assert 'hx-ext="sse"' in template_text
    assert "sse-connect" in template_text
    assert "sse-swap" in template_text
    assert "EventSource" not in template_text
    assert "MutationObserver" not in template_text


def test_chat_template_uses_htmx_sse_stepper_for_immediate_feedback():
    chat_request = (TEMPLATE_ROOT / "components" / "chat_request.html").read_text()

    assert "chat-response-card" in chat_request
    assert "chat-progress-summary" in chat_request
    assert "chat-run-steps" in chat_request
    assert "chat-final-answer-receiver" not in chat_request
    assert "chat-final-answer" in chat_request
    assert "chat-workflow-details" in chat_request
    assert "chat-workflow-summary" in chat_request
    assert "chat-workflow-content" in chat_request
    assert (
        'hx-swap-oob="beforeend:#chat-messages"'
        not in (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()
    )
    assert (
        "chat-final-answer-message"
        not in (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()
    )
    assert (
        "chat-progress-summary-count"
        not in (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()
    )
    assert (
        "Show reasoning trace"
        not in (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()
    )
    assert 'hx-ext="sse"' in chat_request
    assert 'sse-connect="/insights/chat/stream' in chat_request
    assert 'sse-swap="ChatStatus"' in chat_request
    assert 'sse-swap="ChatCompletedStep"' in chat_request
    assert 'sse-swap="ChatActiveStep"' in chat_request
    assert 'sse-swap="ChatFinal"' in chat_request
    assert 'sse-close="done"' in chat_request
    assert "scroll:#chat-messages:bottom focus-scroll:true" in chat_request
    assert "data-stream-url" not in chat_request
    assert "Assistant is writing" not in chat_request
    assert "dot-pulse" in chat_request
    assert chat_request.index("chat-run-completed-steps") < chat_request.index(
        "chat-active-step-slot"
    )
    assert chat_request.index("chat-progress-summary") < chat_request.index(
        "chat-active-step-slot"
    )
    assert chat_request.index("chat-active-step-slot") < chat_request.index(
        "chat-final-answer"
    )


def test_clarification_buttons_submit_selected_message_with_htmx_only():
    final_answer = (TEMPLATE_ROOT / "components/chat_final_answer.html").read_text()

    assert 'hx-post="/insights/chat"' in final_answer
    assert "hx-include=\"#{{ thread_input_id|default('thread-id') }}\"" in final_answer
    assert "hx-vals" not in final_answer
    assert 'name="message"' in final_answer
    assert 'value="{{ option }}"' in final_answer


def test_chat_welcome_copy_does_not_ask_for_direct_questions():
    chat_template = (TEMPLATE_ROOT / "sections/chat.html").read_text()

    assert "Ask a direct question" not in chat_template
    assert "clarify any missing scope, timeframe, or metric" in chat_template


def test_quick_questions_include_scope_timeframe_and_metric():
    chat_template = (TEMPLATE_ROOT / "sections/chat.html").read_text()

    assert "Which hotels are performing best by revenue?" not in chat_template
    assert "Top performing hotels by revenue?" not in chat_template
    assert "Top hotels by latest RevPAR?" in chat_template
    assert "latest portfolio data" in chat_template
    assert "RevPAR" in chat_template


def test_chat_step_template_renders_as_vertical_timeline_item():
    step_template = (TEMPLATE_ROOT / "components/chat_step_item.html").read_text()

    assert "chat-timeline-item" in step_template
    assert "chat-timeline-rail" in step_template
    assert "chat-timeline-node" in step_template
    assert "chat-step-check" not in step_template


def test_chat_step_template_renders_agent_graph_nodes_and_leaves():
    step_template = (TEMPLATE_ROOT / "components/chat_step_item.html").read_text()
    completed_template = (
        TEMPLATE_ROOT / "components/chat_completed_step_item.html"
    ).read_text()

    assert "chat-agent-graph" in step_template
    assert "chat-agent-node" in step_template
    assert "chat-agent-leaves" in step_template
    assert "chat-agent-leaf" in step_template
    assert "{{ agent_name }} agent" in step_template
    assert "chat-agent-graph" in completed_template
