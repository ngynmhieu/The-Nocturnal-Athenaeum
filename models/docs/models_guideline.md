# Models Service — Guideline

The **models service** (`models/`) is a standalone service that **stores, loads,
and runs** models and serves them over an **OpenAI-compatible HTTP API**. The
backend talks to it the same way it would talk to OpenAI — over the network, not
in-process.

It uses the **same modular architecture as the backend** (`core/` + `modules/`),
organized by feature. Here a **feature is a model type**.

---

## 0. Two design principles (read first)

**1. A module is a model type.** Code is grouped by the *kind* of model it serves
(a vertical slice owning its router + service + schemas + manager + model
configs), not by technical role. We only have LLMs today, so there is one module:
**`llm`**. A future embedding/vision/ASR type becomes its own module — added in
one folder, touching nothing else.

**2. A model is data; the module is the code.**

> **Parameter differences → config (JSON). Behavior differences → the module.**

An individual model is a JSON file (no class, no inheritance). Its module holds
the shared code that runs every model of that type by reading the config. Adding
another chat model = a JSON file, zero code.

---

## 1. Why it exists

The model used to live **inside** the backend (`shared/llm/qwen_service.py`),
coupling two things with opposite lifecycles:

| | Model | Backend |
|---|---|---|
| Startup cost | Minutes (load tens of GB onto GPU) | Seconds |
| Change frequency | Rarely | Constantly |

Sharing a process meant every backend restart re-loaded the model. As a separate
service, the backend restarts in seconds while the model stays warm here.

```
┌──────────────────────┐         ┌──────────────────────────────┐
│   BACKEND            │  HTTP   │   MODELS SERVICE             │
│  • API routes        │ ──────► │  • the model (loaded ONCE)   │
│  • business logic    │ ◄────── │  • model configs (JSON)      │
│  • NO model inside   │  reply  │  • OpenAI-compatible API     │
└──────────────────────┘         └──────────────────────────────┘
```

---

## 2. Layout

Started the same way as the backend: a `run_models.py` launcher invoked by
`models/run_models.bat` (alongside `backend/run_backend.bat` / `frontend/run_frontend.bat`; all three are started by the root `run_all.bat`).

```
models/
├── run_models.py                    # launcher (uvicorn) — invoked by run_models.bat
├── requirements.txt
├── docs/models_guideline.md
└── app/
    ├── main.py                      # app factory: create_app(), CORS, lifespan (load default model)
    ├── core/
    │   └── config.py                # service settings (host/port)
    └── modules/
        └── llm/                     # ← the LLM model type (the only module for now)
            ├── router.py            #   endpoints (thin): /v1/chat/completions, /v1/models, /health
            ├── service.py           #   orchestration + OpenAI/SSE formatting
            ├── schemas.py           #   OpenAI request/response shapes
            ├── manager.py           #   model lifecycle: load/unload/swap + generate/stream (llama.cpp)
            ├── processors.py        #   thinking-budget logits processor + stream stripper
            ├── cuda_bootstrap.py    #   preloads the pip CUDA runtime on Windows
            ├── dependencies.py      #   get_llm_service / get_manager
            └── models/              #   DATA: one JSON file per LLM model
                └── qwen3.8-27b.json
        └── image/                   # ← the image model type (Real-ESRGAN upscaler)
            ├── network.py           #   SRVGGNetCompact (PyTorch)
            ├── manager.py           #   lazy weights download + sha256 + inference (CPU)
            ├── service.py / router.py / dependencies.py / config.py
            └── models/              #   DATA: one JSON file per image model
                └── realesr-animevideov3.json
```

**Two model types now:** `llm` (GPU, llama.cpp, loaded at startup) and `image`
(CPU, PyTorch, weights fetched lazily on first request, endpoint
`POST /v1/images/upscale`). See [`modules/image.md`](modules/image.md). Further
types are sibling modules with the same shape, e.g.
`modules/embedding/` (its own `manager.py`, `models/`, `router.py`). Anything that
becomes genuinely cross-module (e.g. a GPU residency coordinator shared by two
types) moves to `app/shared/` **when that need appears** — not before.

**Mapping to the backend** (same conventions):

| Backend | Models service |
|---|---|
| `app/core/config.py` | `app/core/config.py` |
| `app/modules/<feature>/{router,service,schemas,dependencies}.py` | `app/modules/llm/…` |
| `app/shared/llm/qwen_service.py` (model capability) | `app/modules/llm/manager.py` |

---

## 3. Model configs (JSON data)

Each model is one JSON file in `app/modules/llm/models/` — pure configuration, no
behavior. Models are pre-quantized **GGUF** files run by llama.cpp; the
quantization is chosen by picking the file. Example `qwen3.8-27b.json` (trimmed):

```json
{
  "id": "qwen3.8-27b",
  "hf_repo": "unsloth/Qwen3.8-27B-GGUF",
  "gguf_file": "Qwen3.8-27B-UD-Q3_K_XL.gguf",
  "n_gpu_layers": -1,
  "n_ctx": 16384,
  "capabilities": ["chat", "thinking"],
  "max_new_tokens": 2048,
  "description": "Qwen3.8 27B · 262K context · hybrid linear attention · UD-Q3_K_XL.",
  "default": true
}
```

| Field | Meaning |
|---|---|
| `id` | public id clients send in `"model": "..."` |
| `hf_repo` | HuggingFace repo holding the GGUF files |
| `gguf_file` | GGUF filename in that repo (this picks the quantization) |
| `n_gpu_layers` / `n_ctx` | GPU offload (`-1` = all layers) and context window |
| `capabilities` | `chat` / `thinking` / `tools` / `vision`; `thinking` enables the two-phase flow |
| `max_new_tokens` | per-model default generation cap |
| `description` | shown in `GET /v1/models` |
| `default` | `true` on exactly one model → loaded on startup |

The full field list (thinking budget, reasoning effort, sampling) is in
[`modules/llm.md`](modules/llm.md).

**Adding an LLM = drop in a JSON file.** No code, no registration.
(There is no `type` field — the module *is* the type.)

---

## 4. Inside the `llm` module

- **`manager.py`** — owns the model lifecycle: reads `models/*.json`, holds the
  one resident model, loads/unloads/swaps on demand, and runs inference
  (`generate` / `stream`). This is where the llama.cpp machinery lives: GGUF load
  via `Llama.from_pretrained`, the GGUF-embedded chat template rendered with
  `jinja2` (`enable_thinking`, `reasoning_effort`), native streaming, and the
  two-phase thinking budget. One copy, driven by each model's JSON.
- **`service.py`** — `LlmService`: turns an OpenAI request into a call on the
  manager and builds the OpenAI response object / SSE frames. Keeps the router thin.
- **`schemas.py`** — `ChatCompletionRequest` / `ChatMessage` (OpenAI shape).
  Model-specific knobs (`enable_thinking`, `reasoning_effort`) are declared,
  validated fields; OpenAI SDK clients send them via `extra_body`.
- **`dependencies.py`** — FastAPI `Depends` providers (the service / manager).
- **`router.py`** — endpoints only, each a few lines:

  ```python
  @router.post("/v1/chat/completions")
  def chat_completions(req: ChatCompletionRequest,
                       service: LlmService = Depends(get_llm_service)):
      return service.complete(req)
  ```

---

## 5. Configuration

No env file. Configuration lives where it belongs:

| What | Where |
|---|---|
| Per-model settings (repo, GGUF file, context, budgets, sampling) | the model's JSON in `modules/llm/models/` |
| Which model loads on startup | `"default": true` in that JSON |
| Host / port | `core/config.py` defaults (overridable via `MODELS_HOST`/`MODELS_PORT`) |

> Auth: no API key check currently — fine for local single-user. Re-add as a
> dependency in `router.py` if needed.

---

## 6. Running it

From the `models` folder, like the backend (or run `run_all.bat` from the repo root):

```bat
run_models.bat
```

It creates `models/.venv` on first run, installs `requirements.txt`, and starts
the server via `python -m models.run_models` (uvicorn on port 8001). First start
downloads the default model's GGUF (~12.5 GB for Qwen3.8-27B, cached in the
HuggingFace cache afterward) and JIT-compiles the CUDA kernels once. Host/port come from
`core/config.py` (defaults `0.0.0.0:8001`).

---

## 7. API (OpenAI-compatible)

### `GET /health`
```json
{ "status": "ok", "loaded_model": "qwen3.8-27b" }
```

### `GET /v1/models`
```json
{ "object": "list", "data": [ { "id": "qwen3.8-27b", "object": "model", "owned_by": "local", "description": "…", "loaded": true, "capabilities": ["chat", "thinking"] } ] }
```

### `POST /v1/chat/completions`
```json
{
  "model": "qwen3.8-27b",
  "messages": [{ "role": "user", "content": "Hello" }],
  "max_tokens": 512,
  "stream": true,
  "enable_thinking": false
}
```
- `stream: false` → one `chat.completion` object.
- `stream: true` → SSE `data: {chat.completion.chunk}` frames ending `data: [DONE]`.
- `max_tokens` omitted → the model's `max_new_tokens` from its JSON.

---

## 8. How the backend calls it

OpenAI-compatible, so the backend uses the standard `openai` SDK — its
`shared/llm/qwen_service.py` is replaced by a thin client:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8001/v1", api_key="not-needed")
stream = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[{"role": "user", "content": prompt}],
    stream=True,
)
for event in stream:
    delta = event.choices[0].delta.content
    if delta:
        yield delta
```

---

## 9. Trade-offs & future

- **Two processes** to run instead of one.
- **Sync generation** runs in FastAPI's threadpool — fine for single-user. For
  throughput, `manager.py` could move to llama.cpp's own server or `vllm` with no
  change to the router/service.
- **Model swap latency** — switching models unloads/reloads weights.
- **A second model type** = a new sibling module; shared cross-module concerns
  (e.g. GPU residency across types) get extracted to `app/shared/` only then.
