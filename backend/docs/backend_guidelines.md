# Backend Guidelines

## Architecture Overview

The backend is a FastAPI application built as a **modular monolith**. Code is organized **by feature (vertical slices)**, not by technical layer — mirroring the frontend's Feature-Sliced Design. Each feature owns its entire stack (routes, logic, schemas, persistence) in one folder, so a feature can be understood, changed, or removed in one place.

Inside each module, the classic layering still applies: a thin API layer delegates to a service layer, which delegates to lower-level components (LLM engine, database, external APIs).

```
backend/
├── app/
│   ├── main.py            # Composition root: app factory, lifespan, includes module routers
│   ├── core/              # Cross-cutting INFRASTRUCTURE (config, database, security)
│   ├── shared/            # Reusable, business-agnostic code (base classes, exceptions, the LLM engine)
│   └── modules/           # Features — one folder per business domain
│       ├── chat/
│       └── auth/
├── docs/
├── run_backend.py         # Uvicorn entry point
├── requirements.txt
└── .env.backend
```

### Why feature-first, not layer-first

Organizing by layer (`api/`, `services/`, `schemas/` at the top level) smears every feature across many folders — to understand "chat" you would open four folders and mentally filter out everything else. Organizing by feature keeps each domain self-contained:

| Question | Layer-first | Feature-first (this project) |
|---|---|---|
| "Where is all the chat code?" | spread across 4 folders | `modules/chat/` |
| "Add a feature" | edit 4 shared folders | add 1 folder |
| "Remove a feature" | hunt across folders | delete 1 folder |
| Matches the frontend? | No | Yes |

---

## Module Anatomy

Every module under `modules/` follows the same flat, predictable shape. Not every file is required — add one when the feature needs it.

```
modules/chat/
├── router.py          # HTTP endpoints — thin orchestration only
├── service.py         # Business logic and orchestration
├── schemas.py         # Pydantic models — API request/response shapes
├── models.py          # Database models (tables) — persistence shapes
├── dependencies.py    # FastAPI Depends providers + the module's public surface
└── <component>.py     # Optional: extracted complex logic (e.g. prompt_builder.py)
```

- **`router.py`** — Defines an `APIRouter`. Maps HTTP endpoints to service calls. No business logic.
- **`service.py`** — The feature's business logic. Depends on injected components, never instantiates heavy ones itself.
- **`schemas.py`** — Pydantic models for the **API boundary** (what comes in / goes out over HTTP).
- **`models.py`** — Database table definitions for the **persistence boundary**. Kept separate from `schemas.py` so the API shape and the storage shape never blur.
- **`dependencies.py`** — The module's **public surface**. Anything other modules are allowed to use (e.g. `auth`'s `get_current_user`) is exposed here.

Keep modules **flat**. Only break a piece into its own file/subfolder when it genuinely earns it (see *Component Extraction*). Do not replicate the frontend's deep `pages/widgets/features/entities` nesting on the backend.

---

## Folder Responsibilities

### `main.py` — Composition Root
Creates the `FastAPI` instance, registers middleware (CORS), **includes each module's router**, and owns the startup/shutdown lifespan — loading and unloading the model, opening and closing the database, and wiring dependencies together. Modules never import `main.py`; the dependency only flows the other way.

### `core/` — Infrastructure
Cross-cutting infrastructure that must exist before any feature works. Not business logic.

- **`config.py`** — Loads `.env.backend` into a typed Pydantic `Settings` object. All configuration (model name, quantization flag, host, port, tokens, DB URL, Supabase secrets) is read here and **nowhere else**. Every other module imports from `core.config`, never reads env vars directly.
- **`database.py`** — Database engine/session setup and the session dependency.
- **`security.py`** — JWT verification and shared auth dependencies.

### `shared/` — Reusable, Business-Agnostic Code
Code reused across modules that carries no business meaning: base classes, common exceptions, generic helpers, and the **LLM engine**.

- **`llm/`** — The `QwenService` singleton: owns the model and tokenizer lifecycle (loading, one-shot and streaming inference, teardown). It knows about tokenizer templates, quantization, threading, and special-token post-processing. It does **not** know about HTTP, chat history, or application logic. It lives in `shared/` because it is a startup-lifecycle singleton (like the database) and any future feature — an agent, a summarizer — would reuse the same engine.

  > If the engine ever becomes truly chat-only and no other feature could use it, it may move to `modules/chat/llm/`. Until then it is shared infrastructure.

### `modules/` — Features
Each module is a self-contained business domain (a *bounded context*): `chat`, `auth`, and so on. It holds its own routes, logic, schemas, and persistence, and exposes a clean public surface to the rest of the app.

---

## Rules

### API Layer Rules (`router.py`)

- Each `router.py` must be immediately readable — a new team member should understand every endpoint at a glance.
- Route handlers do **not** contain business logic. Their only jobs are:
  1. Extract and validate values from the request (path params, query params, body fields).
  2. Prepare any arguments the service needs.
  3. Call the appropriate service method.
  4. Return the service result as an HTTP response.
- Any `if/else`, loop, or data transformation inside a handler belongs in the service instead.
- `Depends` is acceptable here to supply service instances and the current user.

**Correct:**
```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    user: CurrentUser = Depends(get_current_user),
):
    response = await service.generate_response(user.id, request.messages, request.max_tokens)
    return ChatResponse(response=response.text, elapsed_time=response.elapsed)
```

**Incorrect (logic in router):**
```python
@router.post("/chat")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    # Normalizing messages belongs in the service, not here
    messages = [m for m in request.messages if m.content.strip()]
    if not messages:
        return ChatResponse(response="", elapsed_time=0)
    ...
```

### Service Layer Rules (`service.py`)

The service sits between the router and everything below it (LLM, database, external APIs).

- **Simple logic** goes directly in a service method.
- **Complex logic** is extracted into a dedicated component (see below); the service composes it and stays thin.
- A service depends only on interfaces it is **given via the constructor** — it never instantiates its own heavy dependencies (model, DB session, HTTP clients).
- A service must not import from `router.py`. Dependencies flow downward only: `router → service → llm / db / components`.

**Simple — stays in the service:**
```python
class ChatService:
    async def generate_response(self, messages, max_tokens=None):
        normalized = self._normalize_messages(messages)
        return await self._llm.generate_once(normalized, max_tokens or settings.max_tokens)

    def _normalize_messages(self, messages):
        return [{"role": m.role, "content": m.content} for m in messages]
```

**Complex — extracted to a component:**
```python
# modules/chat/prompt_builder.py  ← extracted component
class PromptBuilder:
    def build(self, messages, system_prompt, context_window): ...

# modules/chat/service.py  ← service stays thin
class ChatService:
    def __init__(self, llm: QwenService, prompt_builder: PromptBuilder):
        self._llm = llm
        self._prompt_builder = prompt_builder
```

### Component Extraction

Extract a piece of logic into its own class/module inside the feature when:
- It has its own testable invariants.
- A method grows beyond ~20–30 lines with distinct sub-steps.
- The same logic is reused across services.

The service composes the component; the component owns the complexity.

### Module Boundary Rules

- **Modules do not reach into each other's internals.** If `chat` needs the logged-in user, it imports `auth`'s public surface (`modules.auth.dependencies.get_current_user`) — never `auth`'s service internals. (This is the backend twin of the frontend's "import only through the public API" rule.)
- A module's **public surface is its `dependencies.py`** (and its `schemas.py` types where another module legitimately needs them). Everything else is private.
- Cross-module communication goes through that surface, or through events/shared abstractions in `shared/` — never through deep imports.

### Schemas vs Models

- **`schemas.py`** = Pydantic models = the **API boundary** (request/response shapes).
- **`models.py`** = database table definitions = the **persistence boundary**.
- Keep them in separate files. Convert between them in the service (or a small mapper component), not in the router.

### Configuration

All environment access goes through `core/config.py`. No module reads `os.environ` or `.env.backend` directly.

---

## Request Flow

```
HTTP Request
  └─→ modules/<feature>/router.py        (thin orchestration)
        └─→ modules/<feature>/service.py (business logic)
              ├─→ shared/llm/            (model inference → SSE stream)
              └─→ core/database          (persistence)
```

## Example: a Chat Message With Persistence

- `modules/chat/router.py` receives the request, gets the current user via `Depends`, delegates to the service.
- `modules/chat/service.py` saves the user message, streams the LLM response, then saves the assistant reply.
- `shared/llm/` performs inference and streams tokens — unaware of HTTP or storage.
- `modules/chat/models.py` defines the `conversations` and `messages` tables.
- `modules/auth/dependencies.py` provides `get_current_user`, consumed by chat through auth's public surface.

This keeps each endpoint clear and keeps every concern in the right place.

---

## When to Move Code

- A helper used by only one feature → keep it inside that module.
- A helper that becomes useful to several modules → promote it to `shared/`.
- Infrastructure needed before features run → `core/`.
- A service method carrying its own complex algorithm → extract a component.

## What Success Looks Like

A new developer should be able to answer instantly:
- Which feature owns this code? → the module folder name.
- Is this API shape or storage shape? → `schemas.py` vs `models.py`.
- Is this reusable or feature-specific? → `shared/`/`core/` vs `modules/`.
- Can another module use this? → only if it is in that module's `dependencies.py`.

If the answers are obvious, the structure is working.
