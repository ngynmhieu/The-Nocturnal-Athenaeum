# Backend Guidelines

## Architecture Overview

The backend is a FastAPI application that serves a local Qwen LLM over HTTP using Streamable HTTP — a single POST endpoint that always responds with an SSE stream. The app is structured into focused layers, each with a single responsibility.

```
backend/
├── app/
│   ├── main.py            # Application factory, startup/shutdown lifecycle
│   ├── api/               # Route handlers — thin orchestration layer
│   ├── core/              # Cross-cutting config and infrastructure
│   ├── llm/               # LLM engine — direct model interaction
│   ├── schemas/           # Pydantic request/response models
│   └── services/          # Business logic and orchestration
├── run_backend.py         # Uvicorn entry point
├── requirements.txt
└── .env.backend
```

### Request Flow

```
HTTP Request
    └─→ api/ (route handler)
            └─→ services/ (orchestration)
                    └─→ llm/ (model inference)
                            └─→ SSE stream (text/event-stream)
```

---

## Modules

### `main.py`
Application factory. Creates the `FastAPI` instance, registers middleware (CORS), attaches the router, and manages the startup/shutdown lifecycle — loading and unloading the model and wiring dependencies together. Nothing else belongs here.

### `api/`
Route handlers. Each file maps HTTP endpoints to service calls. Files are named after the resource they expose (e.g., `agent.py` for chat/agent endpoints). See **API Layer Rules** below.

### `core/`
Cross-cutting infrastructure shared across the app.

- **`config.py`** — Loads environment variables from `.env.backend` into a typed `Settings` object using Pydantic. All configuration (model name, quantization flag, host, port, tokens, HuggingFace token) is read here and nowhere else. Every other module imports from `core.config`, never reads env vars directly.

### `llm/`
Low-level model interaction. Contains the `QwenService` singleton, which owns the model and tokenizer lifecycle: loading, inference (both one-shot and streaming), and teardown. This layer knows about tokenizer templates, quantization, threading for streaming, and special token post-processing. It does not know about HTTP, chat history, or application logic.

### `schemas/`
Pydantic models for all API boundaries. Defines the shape of incoming requests (`ChatRequest`, `Message`) and outgoing responses (`ChatResponse`, `StreamChunk`). No logic lives here — only field definitions, types, validators, and defaults.

### `services/`
Business logic and orchestration between the API layer and lower-level components. See **Service Layer Rules** below.

---

## Rules

### API Layer Rules

All HTTP interface definitions live in the `api/` folder.

- Each file in `api/` should be immediately readable — a new team member must be able to understand what an endpoint does from a quick scan.
- Route handlers do **not** contain business logic. Their only jobs are:
  1. Extract and validate values from the request (path params, query params, body fields).
  2. Prepare any arguments the service needs.
  3. Call the appropriate service method.
  4. Return the service result as an HTTP response.
- If you find yourself writing `if/else`, loops, or data transformations inside a route handler, that logic belongs in the service layer instead.
- Dependency injection (FastAPI's `Depends`) is acceptable here to supply service instances.

**Example — correct:**
```python
@router.post("/chat")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    response = await service.generate_response(request.messages, request.max_tokens)
    return ChatResponse(response=response.text, elapsed_time=response.elapsed)
```

**Example — incorrect (logic in router):**
```python
@router.post("/chat")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    # Normalizing messages belongs in the service, not here
    messages = [m for m in request.messages if m.content.strip()]
    if not messages:
        return ChatResponse(response="", elapsed_time=0)
    response = await service.generate_response(messages, request.max_tokens)
    return ChatResponse(response=response.text, elapsed_time=response.elapsed)
```

---

### Service Layer Rules

The `services/` layer sits between the API layer and all other components (LLM, database, external APIs, etc.).

- **File naming**: every service file must end with `_service.py` (e.g., `chat_service.py`, `user_service.py`).
- **Simple logic**: if the logic is straightforward, implement it directly in the service class method.
- **Complex logic**: if a piece of logic grows complex enough to deserve isolation (e.g., a non-trivial message normalization pipeline, a retry/backoff strategy, a prompt-building algorithm), extract it into a dedicated component — a separate class or module — and have the service compose it. The service itself stays readable; the component owns the complexity.
- A service class should only depend on interfaces it is given (constructor injection), never instantiate its own heavy dependencies.
- Services must not import from `api/` — the dependency always flows downward: `api → services → llm / other components`.

**When to extract a component:**
- The logic has its own testable invariants.
- The method is growing beyond ~20–30 lines and has distinct sub-steps.
- The same logic is reused across multiple services.

**Example — simple, stays in service:**
```python
class ChatService:
    async def generate_response(self, messages, max_tokens=None):
        normalized = self._normalize_messages(messages)
        return await self._llm.generate_once(normalized, max_tokens or settings.max_tokens)

    def _normalize_messages(self, messages):
        return [{"role": m.role, "content": m.content} for m in messages]
```

**Example — complex, extract to a component:**
```python
# services/prompt_builder.py  ← extracted component
class PromptBuilder:
    def build(self, messages, system_prompt, context_window): ...

# services/chat_service.py  ← service stays thin
class ChatService:
    def __init__(self, llm: QwenService, prompt_builder: PromptBuilder):
        self._llm = llm
        self._prompt_builder = prompt_builder

    async def generate_response(self, messages, max_tokens=None):
        prompt = self._prompt_builder.build(messages, SYSTEM_PROMPT, MAX_CONTEXT)
        return await self._llm.generate_once(prompt, max_tokens or settings.max_tokens)
```
