# `llm` Module — Technical Reference

The `llm` module runs text chat LLMs locally with **llama.cpp** (via
`llama-cpp-python`), loading pre-quantized **GGUF** weights, and exposes them over
an OpenAI-compatible HTTP API. It is the only module today; a future model type
(e.g. embedding, vision) would be a sibling module.

For the overall service architecture and why this service exists as a separate
process, see [`docs/models_guideline.md`](../models_guideline.md).

---

## File map

```
modules/llm/
├── config.py          configuration dataclasses (SamplingConfig, ModelConfig)
├── processors.py      decoding-control helpers (thinking budget, stream stripper)
├── cuda_bootstrap.py  preloads the pip-installed CUDA runtime (Windows only)
├── manager.py         model lifecycle + two-phase inference (LlmManager)
├── service.py         OpenAI protocol translation + SSE (LlmService)
├── schemas.py         request/response shapes (Pydantic)
├── router.py          HTTP endpoints (FastAPI, thin)
├── dependencies.py    FastAPI Depends providers
└── models/
    └── qwen3.8-27b.json  one JSON file per model — adding a model = adding a file
```

Call path for a streaming request:

```
POST /v1/chat/completions
  router.chat_completions()
    service.complete(req)
      manager.ensure(req.model)     ← swap to the requested model if needed
      manager.stream(messages, ...) ← two-phase inference
        yield ("thinking", chunk)   ← Phase 1
        yield ("text", chunk)       ← Phase 2
      service._sse()                ← format as SSE frames
```

---

## 1. Configuration (`config.py`)

All per-model settings live in JSON files. `config.py` defines the dataclasses
that load them — there is no code to touch when adding a model.

### `ModelConfig` fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | `str` | required | ID clients send in `"model": "..."` |
| `hf_repo` | `str` | required | HuggingFace repo holding the GGUF files |
| `gguf_file` | `str` | required | GGUF filename inside `hf_repo` (picks the quantization) |
| `mmproj_file` | `str?` | `null` | Vision projector; omit to load text-only |
| `n_gpu_layers` | `int` | `-1` | Layers offloaded to the GPU; `-1` = all |
| `n_ctx` | `int` | `8192` | Context window; its KV cache is allocated in VRAM at load |
| `capabilities` | `str[]` | `["chat"]` | Any of `chat`, `thinking`, `tools`, `vision`; reported by `GET /v1/models` |
| `max_new_tokens` | `int` | `1024` | Token cap for the answer phase |
| `max_thinking_tokens` | `int` | `1024` | Token cap for the thinking phase |
| `thinking_budget_message` | `str` | `"\n\n</think>\n\n"` | Text injected when the thinking budget runs out before `</think>` |
| `default_reasoning_effort` | `str?` | `null` | `low` · `medium` · `xhigh`; used when a request omits `reasoning_effort` |
| `sampling` | `SamplingConfig?` | `null` | Sampler knobs; `null` → greedy decoding |
| `description` | `str` | `""` | Shown in `GET /v1/models` |
| `default` | `bool` | `false` | Exactly one model should be `true` → loaded on startup |

The two-phase thinking flow runs only when `capabilities` contains `"thinking"`.

### `SamplingConfig` fields (inside `"sampling": {}`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `temperature` | `float` | `1.0` | Sampling temperature |
| `top_p` | `float` | `0.95` | Nucleus sampling probability |
| `top_k` | `int` | `20` | Top-K candidates per step |
| `min_p` | `float` | `0.0` | Minimum probability threshold |
| `presence_penalty` | `float` | `0.0` | Flat penalty for tokens already generated; applied natively by llama.cpp |

Defaults match Unsloth's Qwen3.8 thinking-mode recommendation. If `"sampling"`
is omitted from the JSON entirely, generation falls back to greedy decoding.

### Full example (`qwen3.8-27b.json`)

```json
{
  "id": "qwen3.8-27b",
  "hf_repo": "unsloth/Qwen3.8-27B-GGUF",
  "gguf_file": "Qwen3.8-27B-UD-Q3_K_XL.gguf",
  "n_gpu_layers": -1,
  "n_ctx": 16384,
  "capabilities": ["chat", "thinking"],
  "max_new_tokens": 2048,
  "max_thinking_tokens": 1024,
  "default_reasoning_effort": "low",
  "thinking_budget_message": "\n\n(Reasoning budget reached — time to give the final answer.)\n</think>\n\n",
  "sampling": {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5
  },
  "description": "Qwen3.8 27B · 262K context · hybrid linear attention · UD-Q3_K_XL.",
  "default": true
}
```

**Why `UD-Q3_K_XL`:** on a 16 GB GPU it is 12.5 GB and runs fully resident at
~25 tok/s. `UD-Q4_K_XL` (16.7 GB) spills over PCIe and drops to ~10.5 tok/s.
Fitting entirely in VRAM matters more than the extra bit of precision.

---

## 2. Inference — the two-phase thinking flow (`manager.py`)

Qwen3.8 supports a "thinking" mode where the model reasons inside
`<think>…</think>` before giving the final answer.

### Why two phases?

With one call, thinking and answering share one token budget. On hard questions
the model can spend all of it thinking, leaving nothing for the answer. The
two-phase approach gives each stage its own budget:

```
Phase 1 — thinking
  Input:  [prompt] + <think>\n           (rendered by the chat template)
  Output: reasoning text
  Cap:    max_thinking_tokens
  Stop:   </think> stop-string, or budget exhausted

Phase 2 — answer
  Input:  [prompt] + <think>\n[reasoning]</think>\n\n
  Output: the final response
  Cap:    max_new_tokens   ← fresh budget, unaffected by Phase 1
```

Phase 2 continues from a **string** (the phase-1 prompt + reasoning + closing
tag); llama.cpp reuses the matching KV-cache prefix, so Phase 1 is not re-run.

### Prompt rendering

The chat template ships inside the GGUF (`tokenizer.chat_template` metadata).
`manager.py` renders it directly with `jinja2`, passing `enable_thinking`,
`reasoning_effort` and `tools`. There is no tokenizer repo to download and no
transformers dependency.

### Graceful budget handling

**1. `ThinkingBudgetProcessor`** (proactive, preferred)

From 75% of `max_thinking_tokens` onward, the logit of the first `</think>` token
gets a linearly increasing boost — from `+0` at 75% to `+15.0` at 100%. The model
tends to close its thought at a natural boundary before the hard limit.

**2. `_close_thinking`** (safety net)

If Phase 1 ended on the token cap (`finish_reason == "length"`), the manager
appends `thinking_budget_message` (a text nudge + `</think>`) before Phase 2. If
it ended on the stop-string, it re-adds the plain `</think>` that the stop-string
swallowed.

### Streaming specifics

llama.cpp streams natively (`stream=True`), so there is no background thread.
`CloseStripper` filters the Phase 1 stream: it holds back a short tail and drops
`</think>` if it appears, so the caller only ever receives clean thinking text.

---

## 3. Decoding helpers (`processors.py`)

### `ThinkingBudgetProcessor`

Applied in Phase 1 only. Receives llama.cpp's 1-D numpy logits array per token.
Counts tokens as they are generated and, once past `warn_start` (75% of budget),
ramps a boost on the first token of `</think>`:

```
boost = progress * max_boost   where progress ∈ [0, 1] over the final 25%
```

Stateful, so the manager builds a new one for every generation call.

### `CloseStripper`

A stateful stream filter that drops a trailing `</think>` from the thinking
stream. `flush()` must be called after the stream ends to emit any held-back tail.

---

## 4. Model lifecycle (`manager.py`)

`LlmManager` is a module-level singleton (`manager = LlmManager()`). It holds one
model resident at a time and serializes load/swap operations with a threading lock
so an in-flight generation can't race a model swap.

### Load

`ensure(model_id)` checks if the requested model is already resident. If not, it
unloads the current one and loads the new one:

1. `Llama.from_pretrained(hf_repo, filename=gguf_file, n_gpu_layers, n_ctx)` —
   downloads the GGUF into the HuggingFace cache on first use
2. Compiles the GGUF's embedded chat template with `jinja2`
3. Caches the first token ID of `</think>` for `ThinkingBudgetProcessor`

At startup, `app/main.py`'s lifespan loads the default model and calls
`manager.warmup()`, which forces the one-time CUDA PTX→SASS compile so it doesn't
land on the first user request.

### CUDA runtime (`cuda_bootstrap.py`)

The prebuilt `llama-cpp-python` CUDA wheel bundles `ggml-cuda` but not the CUDA
runtime it links against. `requirements.txt` installs `nvidia-cuda-runtime-cu12`
and `nvidia-cublas-cu12`; on Windows, `cuda_bootstrap.bootstrap()` preloads those
DLLs by absolute path before `llama_cpp` is imported. On Linux it is a no-op.

### Swap

Only one model can be resident. Requesting a different `"model"` triggers an
unload → load cycle.

---

## 5. API

### `GET /health`
```json
{ "status": "ok", "loaded_model": "qwen3.8-27b" }
```

### `GET /v1/models`
```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen3.8-27b",
      "object": "model",
      "owned_by": "local",
      "description": "Qwen3.8 27B · 262K context · hybrid linear attention · UD-Q3_K_XL.",
      "loaded": true,
      "capabilities": ["chat", "thinking"]
    }
  ]
}
```

### `POST /v1/chat/completions`

**Request:**
```json
{
  "model": "qwen3.8-27b",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user",   "content": "Explain gravity." }
  ],
  "max_tokens": 512,
  "stream": true,
  "enable_thinking": true,
  "reasoning_effort": "low"
}
```

`enable_thinking` and `reasoning_effort` are declared, validated fields on
`ChatCompletionRequest` (clients using the OpenAI SDK send them via `extra_body`).
An invalid `reasoning_effort` returns 422. Omitted, they fall back to the model's
JSON defaults.

**Non-streaming response (`stream: false`):**
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1718000000,
  "model": "qwen3.8-27b",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "text": "Gravity is ...",
      "thinking": "Let me think through this..."
    },
    "finish_reason": "stop"
  }]
}
```

**Streaming response (`stream: true`):**

```
data: {"choices": [{"delta": {"thinking": "Let me consider..."}}]}
data: {"choices": [{"delta": {"thinking": " the forces involved..."}}]}
data: {"choices": [{"delta": {"text": "Gravity is the attraction..."}}]}
data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}
data: [DONE]
```

`thinking` chunks arrive first (Phase 1), then `text` chunks (Phase 2). The
`text`/`thinking` fields are non-standard OpenAI delta fields; they are
accessible via `choice.delta.model_extra` when using the OpenAI Python SDK.

---

## 6. Tuning guide

| Symptom | Knob | Where |
|---|---|---|
| Model still thinks too long | Lower `max_thinking_tokens`, or `default_reasoning_effort: "low"` | JSON |
| Thinking cut off too early | Raise `max_thinking_tokens` or lower `warn_start` in `ThinkingBudgetProcessor` | JSON / `processors.py` |
| Thinking ends abruptly / incoherent | Raise `max_boost` in `ThinkingBudgetProcessor` | `processors.py` |
| Repetition loops in thinking | Raise `presence_penalty` (up to ~2.0) | JSON `sampling` block |
| Answer too short | Raise `max_new_tokens` | JSON |
| Out of VRAM at load | Lower `n_ctx`, then `n_gpu_layers`, or pick a smaller `gguf_file` | JSON |
| Output too random / hallucinating | Lower `temperature` toward `0.6` | JSON `sampling` block |
| No thinking block wanted | Drop `"thinking"` from `capabilities` or send `"enable_thinking": false` | JSON or request |
