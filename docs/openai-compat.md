# OpenAI-Compatible API

Brigade ships an OpenAI-compatible adapter so that any OpenAI SDK / client
(OpenCode, the `openai` Python and Node libraries, LangChain's OpenAI client,
etc.) can talk to Brigade agents with **no Brigade-specific code**. Each Brigade
agent is surfaced as an OpenAI "model".

Implementation: `app/api/openai_compat_routes.py`, mounted at
`/api/v1/openai/v1`.

## Base URL & Auth

- **Base URL:** `https://<host>/api/v1/openai/v1`
- **API key:** your `BRIGADE_ADMIN_KEY` or a user-scoped API key, sent as the
  standard OpenAI `Authorization: Bearer <key>` header (an `X-API-Key` header is
  also accepted).
- **Model:** the Brigade **agent ID** (e.g. `gunny`, `judge-advocate`,
  `col-finance`). Call `GET /models` to list the agents your key can reach.

When you point a client at a Brigade agent, its persona, system prompt, tools,
and memory are applied automatically on the server side.

## Endpoints

| Method & Path                              | Purpose                                  |
| ------------------------------------------ | ---------------------------------------- |
| `GET  /api/v1/openai/v1/models`            | List agents visible to your key as models|
| `POST /api/v1/openai/v1/chat/completions`  | Chat completion (streaming or not)       |

`/models` filters by per-agent access policy: admins see all agents; other keys
see only the agents their tier/email is allowed to use.

## Example: Python (`openai` SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<host>/api/v1/openai/v1",
    api_key="<BRIGADE_ADMIN_KEY-or-user-key>",
)

resp = client.chat.completions.create(
    model="gunny",                       # a Brigade agent ID
    messages=[{"role": "user", "content": "Draft a status update."}],
)
print(resp.choices[0].message.content)
```

## Example: streaming

```python
stream = client.chat.completions.create(
    model="gunny",
    messages=[{"role": "user", "content": "Summarize today's incidents."}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

## Example: curl

```bash
curl https://<host>/api/v1/openai/v1/chat/completions \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "gunny",
        "messages": [{"role": "user", "content": "Hello"}]
      }'
```

## Tool modes

The adapter adapts to how your client handles tools:

- **No `tools` in the request** — Brigade runs its full server-side tool loop
  (the agent's own tools, memory, persistence). This is the simplest mode.
- **Client sends `tools` and the agent has no server tools** — *passthrough
  mode*: Brigade injects persona + memory into the system prompt but the model
  sees only the client's tools. Your client executes tool calls locally and
  sends `role="tool"` follow-ups back (OpenCode-style).
- **Client sends `tools` and the agent also has server tools** — *dual-layer
  mode*: both sets are available.

## Useful extra fields

These are accepted on the chat-completions body in addition to the standard
OpenAI fields:

- `model_override` — per-call model swap without forking the agent definition.
- `mission_id` — correlation id; forwarded so a subscriber to
  `/api/v1/orchestration/events?mission_id=X` receives only this call's events.
- `case_id` — scopes memory to `{user}__{case}__{agent}` so memories don't bleed
  across cases.

Standard OpenAI fields (`temperature`, `max_tokens`, `stream`, `tool_choice`,
`response_format`, `user`) are supported.
