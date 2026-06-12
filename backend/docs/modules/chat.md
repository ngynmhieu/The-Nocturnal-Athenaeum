# Module: `chat`

> Per-module architecture doc. Mirrors how the frontend documents each module.
> Read `../backend_guidelines.md` first for the rules that govern every module.

## Responsibility

The `chat` module owns one business capability: **turning a conversation history into a streamed LLM response**. It receives chat requests over HTTP, orchestrates the call to the model engine, and streams tokens back as Server-Sent Events.

It does **not** own:
- The model loading/inference internals → that is `shared/llm/` (the `QwenService` engine).
- Configuration → `core/config.py`.
- Authentication / "who is the user" → the future `auth` module's public surface.
- Persistence of conversations → **not yet built** (see *Future*).

---

## Target Structure

```
backend/app/modules/chat/
├── __init__.py
├── router.py          # HTTP endpoints: POST /chat, GET /health
├── service.py         # ChatService — orchestrates conversation → engine
├── schemas.py         # ChatRequest, ChatResponse, Message, StreamChunk
└── dependencies.py    # get_chat_service / wiring (module's DI surface)
```

`models.py` is intentionally **absent for now** — chat has no database tables yet. It will be added when conversation persistence lands.

---

## File-by-File

### `router.py` — HTTP boundary (thin)
Holds the `APIRouter(tags=["chat"])` (no path prefix) and two endpoints:
- `POST /chat` — builds the SSE `StreamingResponse`, delegates streaming to `ChatService`.
- `GET /health` — reports engine readiness via `ChatService.health_check()`.

Stays thin per the API Layer Rules: it only maps the request into a service call and wraps the result in `StreamingResponse`. The message-dict conversion (`[{"role":..., "content":...}]`) currently in the handler should move **into the service** (`_normalize_messages` already exists there) so the router carries no transformation.

### `service.py` — orchestration
`ChatService`, constructed with an injected `QwenService`. Responsibilities:
- `stream_response(...)` — normalize messages, delegate to the engine's `stream_generate`, yield chunks.
- `health_check()` — surface engine readiness.

Depends only on the injected engine (constructor injection). Imports the engine from `shared/llm`, never the other way around.

### `schemas.py` — API boundary
The Pydantic models exactly as they are today: `Message`, `ChatRequest`, `ChatResponse`, `StreamChunk`. These describe what crosses HTTP — not storage.

### `dependencies.py` — DI surface
Holds the provider that hands a ready `ChatService` to the router via `Depends`. This replaces the current module-global `_chat_service` + `set_chat_service` pattern in `agent.py`.

---

## Dependencies (flow downward only)

```
modules/chat/router.py
    └─→ modules/chat/service.py        (ChatService)
            └─→ shared/llm/qwen_service.py   (QwenService engine)

modules/chat/router.py / service.py
    └─→ modules/chat/schemas.py
    └─→ core/config.py                 (defaults like max_tokens)
```

`chat` imports from `shared/` and `core/`. It must never import from `main.py` or reach into another module's internals.

---

## Migration Plan (from the current layer-based layout)

Ordered so the app stays runnable and imports resolve at each step.

1. **Create the engine's new home.** Move `app/llm/qwen_service.py` → `app/shared/llm/qwen_service.py`. Add `shared/__init__.py` and `shared/llm/__init__.py` (re-export `QwenService`). Delete the old `app/llm/`.

2. **Create `modules/chat/`** with `__init__.py`.

3. **Move schemas.** `app/schemas/chat.py` → `modules/chat/schemas.py`. (The old top-level `schemas/` package can be removed once nothing imports it.)

4. **Move the service.** `app/services/chat_service.py` → `modules/chat/service.py`. Update its import to `from app.shared.llm import QwenService`. Pull the router's message-dict conversion into the service.

5. **Move the routes.** `app/api/agent.py` → `modules/chat/router.py`. Update imports to the new sibling modules (`.schemas`, `.service`).

6. **Extract the DI wiring** out of the router into `modules/chat/dependencies.py`.

7. **Update `main.py`** (composition root):
   - Import the engine from `app.shared.llm`, the router from `app.modules.chat`.
   - In the lifespan startup, build `ChatService` and register it through `modules/chat/dependencies.py`.
   - `app.include_router(chat_router)`.

8. **Delete the now-empty** `app/api/`, `app/services/`, `app/schemas/`, `app/llm/` packages.

9. **Smoke test**: start the server, hit `GET /health` and `POST /chat`, confirm streaming still works.

---

## Improvements to fold in during the move (optional but recommended)

- **Replace the global-singleton DI** (`_chat_service` module global + `set_chat_service`) with FastAPI `app.state` or a proper dependency provider. The current pattern works but hides wiring in module globals; `app.state.chat_service` read by a `Depends` provider is cleaner and testable.
- **Migrate off deprecated `@app.on_event`** to the modern `lifespan` context manager while touching `main.py`.
- **Push the router's transformation into the service** so the handler has zero logic (per API Layer Rules).

---

## Future (when persistence + auth arrive)

- `models.py` — `conversations` and `messages` tables (see the auth & persistence plan).
- `service.py` gains: save user message → stream → save assistant reply.
- Endpoints gain `user = Depends(get_current_user)` from `modules/auth/dependencies.py`.
- A `health`/system concern may move out of `chat` into its own small module, since engine readiness is not really chat business logic.
