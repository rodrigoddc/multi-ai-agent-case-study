# Token & Cost Tracking in Langfuse

This project captures LLM token usage and cost in Langfuse traces for every agent
invocation.  Both the OpenRouter and llama.cpp adapters expose a `last_usage`
dict after each `generate()` call, which `PortBackedChatModel._agenerate` reads
and embeds into the `AIMessage.usage_metadata` that Langfuse's
`CallbackHandler` picks up.

## What is tracked

| Field              | OpenRouter                 | llama.cpp (estimate) |
|--------------------|----------------------------|----------------------|
| `input_tokens`     | From API response          | `len(input) // 4`    |
| `output_tokens`    | From API response          | `len(output) // 4`   |
| `total_tokens`     | From API response          | sum of above         |
| `cost`             | From OpenRouter `usage`    | *not available*      |

## Architecture

```
User request
  └─ LangGraph (config["callbacks"] = [LangfuseHandler])
      └─ GandalfAgent
          └─ PortBackedChatModel._agenerate
              └─ LLMAdapter.generate()
                  ├─ OpenRouterAdapter → ChatOpenRouter.ainvoke()
                  │     └─ sets self.last_usage from AIMessage metadata
                  └─ LlamaCppAdapter → raw HTTP POST
                        └─ sets self.last_usage from char-length estimate
              └─ builds ChatResult with AIMessage(usage_metadata=...)
  └─ Langfuse CallbackHandler.on_llm_end()
        └─ reads usage_metadata → stores tokens & cost in trace
```

### OpenRouter (paid)

Returns real token counts and cost from the OpenRouter API.
`ChatOpenRouter._create_chat_result` already extracts `usage` from the
response; the adapter stores it in `self.last_usage`.

### llama.cpp (local)

No token usage is returned by the server, so the adapter estimates:

```python
input_tokens  = max(1, len(system_prompt + "\n" + user_message) // 4)
output_tokens = max(1, len(text) // 4)
```

The `// 4` factor is a rough average for English text (≈4 chars per token).
This is visible in Langfuse as an estimate only — do not use for billing.

## If the Langfuse trace shows empty usage

1.  **OpenRouter route** — confirm the model returns `usage` in its API
    response.  Most paid models do; some free/trial endpoints may omit it.
2.  **llama.cpp route** — usage is always estimated.  If the estimate is
    wildly off you can tune the `// N` factor in
    `src/app/infrastructure/adapters/llamacpp_adapter.py`.
3.  **Custom models** — add a model definition in the Langfuse UI or API
    so Langfuse can infer tokens/cost from the `model` string alone (see
    [Langfuse docs](https://langfuse.com/docs/usage-tracking/custom-model-definitions)).

## Viewing in Langfuse

1.  Open the Langfuse dashboard (http://localhost:3000 for local).
2.  Navigate to **Traces**.
3.  Click any trace → expand the LLM **generation** observation.
    - **Usage** tab shows input / output tokens.
    - **Cost** tab shows USD cost (OpenRouter only).
4.  The **Models** page aggregates total spend across all traces.

## Adding a new LLM adapter

If you add a third provider adapter:

1.  Set `self.last_usage` after each `generate()` call — a dict with
    `input_tokens`, `output_tokens`, `total_tokens`, and optionally `cost`.
2.  `PortBackedChatModel._agenerate` reads it automatically via
    `getattr(self.llm, "last_usage", None)`.
3.  Langfuse captures it on the next `on_llm_end` callback.

No further wiring is needed.
