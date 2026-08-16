# Plan — Replacing the `models` engine with Unsloth GGUF + llama.cpp

**Decision:** full replacement. Qwen3.5-9B, transformers, bitsandbytes and torch
all get deleted. One model, one engine, one code path.

---

## 0. First, a correction to the premise

> "Currently I am working on with raw HF model and quantize it by python script"

Not quite what the code does, and the difference matters for the plan.

There is **no quantization script and no quantized artifact**. `manager.py:100-119`
loads the raw BF16 repo and hands `BitsAndBytesConfig` to `from_pretrained`, so
bitsandbytes quantizes **on the fly, in memory, on every single load**:

```python
kwargs["quantization_config"] = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4", ...
)
```

Three consequences:

1. You download and read the **full BF16 weights every time** (9B ≈ 18 GB today;
   Qwen3.8-27B would be **≈ 56 GB**).
2. Startup cost is paid on every service start and every model swap.
3. `bnb` NF4 is a *generic round-to-nearest* scheme. Unsloth's `UD-*` "Dynamic"
   quants assign bit-width per tensor, so at equal file size they retain more
   accuracy.

So the move isn't "script → different script". It's **"quantize at load time" →
"download an already-quantized artifact"**.

---

## 1. What you have today

```
models/  (FastAPI, :8001, OpenAI-compatible)
└── app/modules/llm/
    ├── config.py       ModelConfig / SamplingConfig  ← JSON-driven, no code per model
    ├── manager.py      LlmManager singleton  ← ALL transformers coupling lives here
    ├── processors.py   ThinkingBudgetProcessor, PresencePenaltyLogitsProcessor, CloseStripper
    ├── service.py      OpenAI shapes + SSE   ← engine-agnostic
    ├── router.py       thin endpoints        ← engine-agnostic
    └── models/qwen3.5-9b.json
```

**The good news:** the transformers dependency is almost perfectly quarantined.
`service.py`, `router.py`, `schemas.py`, `dependencies.py` never touch torch. The
blast radius of an engine swap is **`manager.py` + `processors.py`, and nothing else.**

Your own guideline already predicted this — `models_guideline.md` §9:

> "`manager.py` can be swapped to a `vllm`/`sglang` backend with no change to the
> router/service or the JSON configs."

This plan is that sentence, cashed in.

---

## 2. The real driver: 27B does not fit your GPU the way 9B does

Hardware: **RTX 5060 Ti, 16 GB VRAM** · Ryzen 5 7500X3D (6c/12t) · **32 GB RAM**.

`manager.py`'s docstring encodes the current assumption — *"Keeps one model
resident on the GPU (16 GB fits one)"*. That assumption holds for 4-bit 9B. It
**breaks for 27B**:

| Path | Memory | Fits 16 GB? |
|---|---|---|
| transformers + bnb NF4, 27B | ~17-19 GB | ❌ over by 2-3 GB |
| llama.cpp `UD-Q4_K_XL` | ~17-19 GB | ⚠️ over, but offloads cheaply |
| llama.cpp `UD-Q3_K_XL` | ~13-16 GB | ✅ fits fully |

Both overflow. The difference is **what happens when you overflow**:

- **bitsandbytes + `device_map="auto"`** spills whole layers to CPU and moves
  tensors across PCIe per token. Throughput collapses — often 5-10x slower.
- **llama.cpp** was built for the split. `--n-gpu-layers` keeps most layers on the
  GPU and runs the remainder on CPU with quantized kernels tuned for it.

**This is the actual justification for the migration.** Not "Unsloth is nicer" —
llama.cpp is what makes a 27B model *viable at all* on a 16 GB card.

One tailwind: Qwen3.8's `layer_types` is **48 linear-attention + 16 full-attention**
layers (3:1). KV cache grows with the 16 full-attention layers, not all 64, so
context is far cheaper than a normal 27B dense model. Still — don't go near the
262K max on this box.

---

## 3. "The Unsloth method" is three different things — pick deliberately

| | What it is | Fit for this project |
|---|---|---|
| **A. Unsloth Desktop** | GUI app (llama.cpp/MLX inside) | ❌ **Rejected.** It's a *replacement* for your models service, not a component. Your backend needs a headless HTTP endpoint, and `models/Dockerfile` builds a deployable image. Fine for *manually evaluating* a quant; not part of the architecture. |
| **B. Unsloth pre-quantized safetensors** (`-FP8` / `-NVFP4`) | Drop-in `hf_repo` swap | ⚠️ Needs vLLM/SGLang, effectively **Linux-only**. You develop on Windows. Doesn't solve the 16 GB overflow. |
| **C. Unsloth GGUF + llama.cpp** (`unsloth/Qwen3.8-27B-GGUF`) | New engine in `manager.py` | ✅ **Chosen.** |

To be explicit, since "Unsloth vs llama.cpp" is a false choice — they're different
layers of one stack:

```
unsloth/Qwen3.8-27B-GGUF     ← WHO quantized the weights (Unsloth)   ✅
    └── UD-Q4_K_XL.gguf      ← the file format           (GGUF)      ✅
            └── llama.cpp    ← WHAT runs the file        (engine)    ✅
                    └── Unsloth Desktop  ← GUI wrapper               ❌
```

The `UD-` prefix is the whole reason to use their repo over self-quantizing or
another publisher: bit-width varies per tensor, so quality holds better at equal
file size. You already follow their guidance — [config.py:20-21](models/app/modules/llm/config.py#L20-L21)
cites *"Unsloth's Qwen3.5 thinking-mode recommendation"*. This extends that from
their advice to their weights.

---

## 4. What survives the deletion

Auditing `processors.py` and `manager.py` against llama.cpp:

| Asset | Fate | Notes |
|---|---|---|
| `PresencePenaltyLogitsProcessor` | 🗑️ **Delete** | llama.cpp has `presence_penalty` **natively**. Your file says transformers has no native one — that's why you wrote it. llama.cpp does. |
| `_run_stream` thread + `holder` dict | 🗑️ **Delete** | `TextIteratorStreamer` + daemon thread + `holder["out"]` (`manager.py:154-174`) exists only because `model.generate()` blocks. llama.cpp yields natively. **Removes the most fragile code in the module.** |
| `_auto_from_pretrained` fallback | 🗑️ **Delete** | The `AutoModelForImageTextToText` → `AutoModelForCausalLM` dance is a transformers-only problem. |
| `BitsAndBytesConfig` block + `quantize` field | 🗑️ **Delete** | Quant is baked into the `.gguf` filename now. |
| `torch` import in `manager.py` | 🗑️ **Delete** | Along with `torch.cat`, `torch.ones_like`, `torch.cuda.empty_cache`. |
| Two-phase thinking (Phase 1 → Phase 2) | ✅ **Keep, simpler** | Currently needs `torch.cat` on token tensors (`_append_close`, `manager.py:176-183`). On llama.cpp you rebuild the Phase 2 prompt as **plain text** — no tensor surgery. |
| `CloseStripper` | ✅ **Keep** | Pure string filter, engine-agnostic. |
| **`ThinkingBudgetProcessor`** | ⚠️ **RISK #1** | Needs per-step logit access. `llama-cpp-python` exposes `logits_processor`, so it *should* port — **must be proven in Phase 0**. Note: with `llama-server` as a subprocess this would be **impossible**; that's why this plan uses the in-process binding. |
| Vision / `mmproj-F16.gguf` | ⚠️ **RISK #2** | llama.cpp needs a per-architecture vision handler and `qwen3_5` is days old. May not be supported yet. |

**Net: you delete substantially more than you add.**

> **The engine choice binds every capability.** `LlmManager` holds one model
> resident and 16 GB cannot hold a 27B twice, so whichever engine you pick must
> serve *all* capabilities you want live at once. There is no "text on llama.cpp,
> vision on transformers" once transformers is gone.

---

## 5. Design: one engine, no seam

An earlier draft proposed an `engines/` abstraction keeping transformers as a
fallback. **That's now deleted from the plan.** An engine seam that only ever
holds one engine is speculative abstraction — it earns nothing and costs a layer
of indirection on every call.

```
modules/llm/
├── config.py        ModelConfig (gguf fields; engine/quantize fields gone)
├── manager.py       LlmManager — llama.cpp directly, no protocol layer
├── processors.py    ThinkingBudgetProcessor, CloseStripper   (PresencePenalty deleted)
├── toolcalls.py     ← new: parse Qwen's <tool_call> XML → OpenAI tool_calls
├── content.py       ← new: normalise multimodal message content parts
├── service.py       unchanged
├── router.py        unchanged
├── schemas.py       extended (tools, vision, reasoning)
└── models/
    └── qwen3.8-27b.json      ← the only model
```

`manager.py` keeps its public surface (`ensure` / `generate` / `stream` /
`list_configs` / `current_model_id`), so **`service.py`, `router.py`,
`dependencies.py`, `main.py` change zero lines** for the engine swap itself.

### Your fallback is git, not an abstraction

Deleting the working 9B path means **you have no runtime fallback**. That's the
right call — but it makes sequencing critical:

> **Do not delete the transformers path until llama.cpp is proven working on your
> machine.** The old code lives in git history (`c1b4f2c` and earlier); recovering
> it is `git revert`, not a rewrite. Phase 0 exists precisely so the deletion
> happens *after* you're across the gap, never before.

### `ModelConfig` changes (`config.py`)

**Removed:** `quantize`, `supports_thinking` (subsumed by `capabilities`).

**Added:**

| Field | Default | Meaning |
|---|---|---|
| `gguf_file` | required | e.g. `"Qwen3.8-27B-UD-Q4_K_XL.gguf"` |
| `mmproj_file` | `None` | vision projector — omit to load text-only |
| `n_gpu_layers` | `-1` | `-1` = all; lower it to spill to RAM |
| `n_ctx` | `8192` | KV cache budget — the real VRAM constraint |
| **`capabilities`** | `["chat"]` | `chat` · `thinking` · `tools` · `vision` |

### `capabilities` — the one field worth keeping

This is what "spends the room". `GET /v1/models` already returns a catalog;
`capabilities` makes it *useful*:

```json
{ "id": "qwen3.8-27b", "capabilities": ["chat", "thinking", "tools", "vision"] }
```

Curator only offers MCP tools when `"tools"` is present; the composer only shows
image upload when `"vision"` is present. It also gives you a **staged rollout
switch** — ship with `["chat", "thinking"]`, add `"tools"` when Phase 6 lands, add
`"vision"` if Phase 7 unblocks. Clients adapt with no redeploy.

> No `tool_format` field. With exactly one model, parser selection is speculative —
> hardcode the Qwen3.8 syntax in `toolcalls.py`. Adding the field later is trivial;
> carrying it now repeats the mistake the engine seam would have made.

Target JSON — the **only** file in `models/`:

```json
{
  "id": "qwen3.8-27b",
  "hf_repo": "unsloth/Qwen3.8-27B-GGUF",
  "gguf_file": "Qwen3.8-27B-UD-Q3_K_XL.gguf",
  "mmproj_file": "mmproj-F16.gguf",
  "n_gpu_layers": -1,
  "n_ctx": 16384,
  "capabilities": ["chat", "thinking", "tools", "vision"],
  "max_new_tokens": 2048,
  "default_reasoning_effort": "medium",
  "max_thinking_tokens": 2048,
  "thinking_budget_message": "\n\n(Reasoning budget reached — time to give the final answer.)\n</think>\n\n",
  "sampling": {
    "temperature": 1.0, "top_p": 0.95, "top_k": 20,
    "min_p": 0.0, "presence_penalty": 1.5
  },
  "description": "Qwen3.8 27B · vision · tools · hybrid linear attention · UD-Q4_K_XL.",
  "default": true
}
```

> ⚠️ **Revised after Tier 2 measured 10.5 tok/s.** An earlier draft said to raise
> `max_thinking_tokens` to 2048 because `reasoning_effort` defaults to `xhigh`.
> **At 10 tok/s that is over three minutes of silence before the answer starts.**
> Throughput changes the calculus: prefer `default_reasoning_effort: "low"` and a
> budget nearer **512-1024**. Generating fewer tokens is the single biggest lever
> on *felt* responsiveness, and it costs nothing.

#### Measured `n_gpu_layers` — why not `-1`

Two sweeps on `UD-Q4_K_XL`, `n_ctx=8192` (tok/s, generation):

| layers | 40 | 48 | 52 | 56 | 58 | 59 | **60** | 61 | 62 | -1 (65) |
|---|---|---|---|---|---|---|---|---|---|---|
| tok/s | 4.3 | 5.9 | 7.2 | 8.8 | 8.7 | 8.9 | **10.5** | 6.6 | 6.0 | 5.0 |

**A sharp peak at 60, not a gradient.** Above it, Windows WDDM lets the allocation
succeed and then silently pages VRAM over PCIe — far slower than honestly running
layers on the CPU. `-1` is roughly half speed *and* erratic (one run measured 1.7).

Things that did **not** help, so don't bother:

- **`flash_attn=True`** — 10.8 vs 10.3 tok/s at 60 layers. Noise.
- **`n_ctx` 4096 vs 8192** — 10.4 vs 10.8. No gain, which also implies **KV-cache
  quantization won't help**: the cache is not the binding constraint, the weights are.

VRAM sits pinned at ~16000 / 16310 MiB in nearly every config. The card is
saturated no matter how it's tuned — 16.69 GB of weights simply exceed 16.3 GB of
VRAM, and every knob is a workaround for that one fact.

#### ✅ RESOLVED: Q3 wins decisively — use `UD-Q3_K_XL`

`UD-Q3_K_XL` is **12.52 GB**, so all 65 layers fit with room to spare. No CPU
offload, no paging:

| Quant | best config | VRAM | tok/s |
|---|---|---|---|
| `UD-Q4_K_XL` (16.69 GB) | `n_gpu_layers=60` | 15960 | 10.5 |
| **`UD-Q3_K_XL` (12.52 GB)** | **`n_gpu_layers=-1`, `n_ctx=16384`** | 14481 | **25.0** |

**2.4× faster.** And unlike Q4, `-1` is now correct — everything fits, so there is
no cliff to avoid.

**Quality holds.** Q3 answered the same trick question correctly
(*"**9 sheep are left.** … all the sheep ran away *except* 9"*) in **3.6s total**,
versus ~15s for Q4's thinking phase alone, and emitted identical well-formed
`<tool_call>` XML.

**Context is now nearly free.** `n_ctx` 8192/16384/32768 all measure ~24-26 tok/s.
32768 fits but at 15923 MiB it sits on the paging cliff — **16384 (14481 MiB) is
the safe choice**, and it doubles the context the plan originally budgeted.

#### ⚠️ Beware PTX JIT on first run

The cu125 wheel ships kernels as **PTX**, which the driver compiles to SASS on
first use for sm_120. That compile is one-time but expensive, and it silently
corrupted two earlier measurements:

| Measurement | Real? |
|---|---|
| Q4 tier2, 1.7 tok/s | ❌ cold JIT + paging |
| Q3 first config, 4.9 tok/s | ❌ cold JIT (Q3_K kernels differ from Q4_K) |
| Same Q3 config re-run | ✅ 23.5 → 25.5 → **25.8** tok/s |

Results cache to `%APPDATA%\NVIDIA\ComputeCache` and persist across restarts, but:

- **The first request after a fresh install will be ~5× slow.** Warm the model with
  a throwaway generation in `main.py`'s lifespan handler, not on a user's request.
- **Docker starts with an empty cache every run.** Mount a volume for it, or accept
  a slow first request per container.
- Never benchmark a cold cache — always discard the first run.

---

## 5b. The API contract decision (settle before writing code)

Your SSE deltas are **non-standard**. `service.py:75` emits:

```python
delta = {"thinking": chunk_text} if chunk_type == "thinking" else {"text": chunk_text}
```

Real OpenAI uses `content`, and `llm.md` §5 notes clients must dig into
`choice.delta.model_extra` to read your `text` field. Fine when the only extension
was `thinking`. **It stops being fine once tool calls arrive** — your backend uses
the official `openai` SDK (`models_guideline.md` §8), which parses standard
`tool_calls` natively but cannot see `text` at all.

| Today | Change to | Why |
|---|---|---|
| `delta.text` | **`delta.content`** | SDK populates it natively; deletes client-side `model_extra` handling |
| `delta.thinking` | **`delta.reasoning_content`** | De-facto cross-provider standard for reasoning traces |
| *(none)* | **`delta.tool_calls`** | OpenAI's exact shape — free SDK parsing |
| `finish_reason` always `"stop"` | `"tool_calls"` when a call was emitted | SDK agent loops branch on this |

Breaking for the frontend, so land it deliberately — but land it *before* tools,
not after. Retrofitting once Curator depends on it costs far more.

---

## 6. Phases

### Phase 0 — Spike (load-bearing; nothing gets deleted until this passes)

**Do not touch `models/` yet.** Throwaway code in the scratchpad. Because there is
no fallback engine, **this is the go/no-go for the whole plan.**

Tiered by cost, cheapest kill-shots first. **The two scariest items need no Qwen
download at all** — a ~1 GB model proves them.

#### Tier 0 — ~15 minutes, no downloads, no GPU

1. **Does a `llama-cpp-python` wheel install at all?** `pip install llama-cpp-python`.
   If a prebuilt CUDA wheel exists for your Python + CUDA, you skip the compile
   entirely.
2. **⭐ Does its bundled llama.cpp know `qwen3_5`?** *This is the real gate.*
   `llama-cpp-python` pins a specific llama.cpp commit. Qwen3.8 is days old — if
   the pin predates `qwen3_5` support, nothing else matters. Check the bundled
   version against llama.cpp's release notes.
3. **Does `transformers` render the chat template without torch?** Import
   `AutoTokenizer` and call `apply_chat_template` with torch *absent*. Decides
   whether `transformers` survives Phase 2 as a tokenizer-only dependency. Fallback
   is `jinja2` + the repo's `chat_template.jinja` — **do not hand-reimplement that
   template**, it's macro-heavy Jinja.

#### Tier 1 — ~1 hour, tiny GGUF (~1 GB), still no Qwen download

4. **⭐ Does `logits_processor` fire?** Load any small GGUF, attach a processor that
   boosts one token id, confirm the callback runs per step and the boost lands.
   **Go/no-go for `ThinkingBudgetProcessor`** — and it's architecture-independent,
   so a 0.6B model answers it.
5. **Prove the two-phase pattern.** Generate → append text → generate again from the
   extended prompt string. This replaces `torch.cat`; verify the seam works on
   *any* model before betting the 27B on it.

#### Tier 2 — half a day, the real model (~17 GB download)

6. **Build with CUDA if Tier 0 needed it:**
   ```
   $env:CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120"
   pip install llama-cpp-python --no-binary llama-cpp-python
   ```
   Needs CUDA toolkit + MSVC build tools. Mainline llama.cpp is sufficient — the
   `unslothai/llama.cpp` **`iq1-narrow` branch is only for `IQ1_XXXS`**, which
   applies to the 2.4T MoE model, not the 27B. Standard quants use upstream.
7. **Measure, don't assume.** Download **both** `UD-Q4_K_XL` and `UD-Q3_K_XL`.
   Compare Q4-spilling-to-RAM against Q3-fully-resident. Tune `n_gpu_layers` down
   until it stops thrashing. *(Tuning, not a gate.)*
8. **Tools:** confirm the `# Tools` block renders from GGUF metadata.
9. **Vision:** load with `mmproj-F16.gguf`, send one image. Unsloth's official build
   includes `llama-mtmd-cli` as a target, so multimodal is plausibly supported.

#### Failure routes

| Fails | Consequence |
|---|---|
| (2) arch unsupported | **Hard stop.** Rebuild `llama-cpp-python` against newer llama.cpp, or wait for a release. Do not fight it — the model is days old. |
| (4) no logit access | **Fork in the road.** Either accept a hard thinking cap with only `_append_close` (losing graceful closes), or stay on transformers. Also rules out the `llama-server`-subprocess alternative, which has no logit access by design. |
| (9) vision unsupported | Survivable — ship Phases 1-5, declare `capabilities` without `"vision"`, gate Phase 6 on upstream. **Do not let it block the migration.** |
| (8) template drops tools | Inject the tool preamble manually in `toolcalls.py`. Annoying, not fatal. |

---

#### ✅ Tier 0 RESULTS — run 2026-08-15, all passed

Scripts in `scratchpad/spike/`. Nothing downloaded beyond a 48 MB ranged read of
the GGUF header.

| Check | Result |
|---|---|
| Prebuilt wheel exists | ✅ `llama-cpp-python 0.3.34` from the **cu125** index. Wheels are `py3-none-win_amd64` — **ABI-agnostic**, so Python 3.14 is fine. **No compile, no CUDA toolkit.** |
| Blackwell works | ✅ `found 1 CUDA devices … RTX 5060 Ti, compute capability 12.0, VRAM 16310 MiB`. A cu125 build drives sm_120 fine. |
| **`qwen35` supported** | ✅ GGUF says `general.architecture = qwen35`; `llama.dll`'s arch table contains `qwen35`. **The model loads.** |
| Chat template present | ✅ 9,993 chars embedded in GGUF metadata. |
| Template renders standalone | ✅ **plain `jinja2`, no transformers** (details below). |

**Confirmed from GGUF metadata** — matches the HF config exactly:
`block_count 65` (64 + 1 MTP, `nextn_predict_layers = 1`) · `full_attention_interval 4`
(→ 16 full-attention layers, validating the KV-cache math in §2) ·
`context_length 262144` · `head_count 24 / head_count_kv 4` · `key/value_length 256`
· `ssm.*` keys for the Gated DeltaNet layers.

**Template behaviour, verified by rendering:**

```
enable_thinking=True   → ends with "<|im_start|>assistant\n<think>\n"   ← two-phase prefill WORKS
enable_thinking=False  → emits "<think>\n\n</think>\n\n"  (pre-closed)
reasoning_effort="low" → injects the instruction into the system prompt
tools=[...]            → renders "# Tools" + JSON schemas + <tool_call> format
system message w/ image→ raises "System message cannot contain images."
```

#### Two findings that change the plan

**1. `transformers` can be deleted entirely — not kept as tokenizer-only.**
The template ships *inside* the GGUF, and `jinja2` renders it with only a
`raise_exception` global supplied. Open question resolved: **drop `transformers`,
add `jinja2`.**

**2. The CUDA runtime must be installed AND explicitly preloaded.**
The wheel ships `ggml-cuda.dll` (902 MB) but **not** the CUDA runtime it links
against. Torch was satisfying that by accident; deleting torch breaks it. The
failure is `Failed to load shared library 'llama.dll'` — which names the wrong
culprit and is genuinely confusing to debug.

> ⚠️ **`os.add_dll_directory()` alone is NOT enough.** Verified the hard way: it
> still failed. Windows does not reliably search user directories when resolving a
> *transitive* dependency of a ctypes-loaded DLL. The runtime must be **preloaded
> by absolute path** so it is already in the process.

`models/app/modules/llm/cuda_bootstrap.py`, imported before `llama_cpp`:

```python
import ctypes, glob, os, sys

# cublas depends on cublasLt, so load order matters.
_RUNTIME = ("cudart64_*.dll", "cublasLt64_*.dll", "cublas64_*.dll")

def bootstrap() -> None:
    roots = glob.glob(os.path.join(sys.prefix, "Lib", "site-packages",
                                   "nvidia", "*", "bin"))
    for root in roots:
        os.add_dll_directory(root)
    for pattern in _RUNTIME:            # add_dll_directory is insufficient alone
        for root in roots:
            for path in glob.glob(os.path.join(root, pattern)):
                ctypes.CDLL(path)
```

Confirmed working: `preloaded ['cudart64_12.dll', 'cublasLt64_12.dll', 'cublas64_12.dll']`.

**Resulting `requirements.txt`:**

```
--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125
llama-cpp-python==0.3.34
nvidia-cuda-runtime-cu12
nvidia-cublas-cu12
jinja2

fastapi>=0.95.0
uvicorn[standard]>=0.22.0
```

No `torch`, no `torchvision`, no `bitsandbytes`, no `accelerate`, no `transformers`.

---

#### ✅ Tier 1 RESULTS — run 2026-08-15, all passed

Proven on `Qwen2.5-0.5B-Instruct-Q4_K_M` (~400 MB). Both checks are
architecture-independent, so no 27B download was needed.

**(4) `logits_processor` — PASS. This was the plan's biggest risk; it's gone.**

```
invocations      : 12          (one per generated token)
arg types/shapes : ndarray, (151936,)      ← full vocab logits, mutable
baseline output  : 'Three common colours are red, blue, and yellow.'
boosted output   : 'Three common colours purple purple purple purple ...'
```

A processor that warms up for 3 tokens then adds `+100.0` to one token's logit
takes over completely — exactly the mechanism `ThinkingBudgetProcessor` uses to
ramp `</think>`. **The port is viable; keep the graceful-close behaviour.**

**(5) two-phase via text continuation — mechanism PASS, semantics untested.**
Generating, concatenating the result plus a close string, and generating again
from the extended prompt works — **`torch.cat` and `_append_close`'s tensor
surgery are replaceable by string concatenation.** `stop=["</think>"]` also works.

> ⚠️ Honest caveat: Qwen2.5-0.5B has no thinking training, so it ignored `<think>`
> and simply answered both times. The *plumbing* is proven; the actual
> thinking→answer behaviour can only be validated on the 27B in Tier 2.

**(bonus) native streaming — PASS.** 12 chunks, reassembling to the identical
text. Confirms `_run_stream`'s daemon thread + `holder` dict + `TextIteratorStreamer`
can all be deleted outright.

#### Still unproven — Tier 2 only

- **Throughput**, and `UD-Q4_K_XL`-with-offload vs `UD-Q3_K_XL`-resident.
- **Real two-phase thinking behaviour** on a model actually trained for it.
- **Vision** via `mmproj-F16.gguf`. Encouraging: the wheel ships `mtmd.dll`
  (llama.cpp's multimodal library) and the template renders `vision_start`.

**Nothing blocking remains.** Tier 2 is measurement and one gated capability —
Phase 1 can begin.

### Phase 1 — Replace the engine

One commit, on a branch. `manager.py` is rewritten against `llama-cpp-python`:

- `_load_locked` → `Llama.from_pretrained(repo_id, filename=cfg.gguf_file, ...)`
- `_sampling_kwargs` → native params, **`presence_penalty` included**
- `_run_stream` → deleted; use `stream=True` directly
- `_append_close` → string concatenation instead of `torch.cat`
- `ThinkingBudgetProcessor` → ported to the numpy-array signature
- `PresencePenaltyLogitsProcessor` → **deleted**

Add `qwen3.8-27b.json`. **Verify streaming, thinking, and the two-phase budget all
work end-to-end before proceeding.**

### Phase 2 — Delete Qwen3.5 and the HF stack

Only once Phase 1 is verified running:

| Delete | Where |
|---|---|
| `qwen3.5-9b.json` | `modules/llm/models/` |
| `torch`, `torchvision`, `--extra-index-url` (pytorch) | `requirements.txt` |
| `bitsandbytes`, `accelerate` | `requirements.txt` |
| `quantize` / `supports_thinking` fields | `config.py` |
| `transformers` | ✅ **confirmed deletable** — Tier 0 proved `jinja2` renders the GGUF-embedded template standalone |

This is where the payoff lands: **torch + cu128 is multiple GB**. Dropping it
shrinks the venv and the Docker image dramatically.

### Phase 3 — Packaging

- `Dockerfile`: CUDA base is already right, but `llama-cpp-python` now needs
  **compilation** — add MSVC/gcc + CMake, and use a **multi-stage build** so build
  tools don't ship in the runtime image. Set `CMAKE_CUDA_ARCHITECTURES` for your
  target GPU. Keep `HF_HOME=/cache/huggingface` so GGUFs cache on a mounted volume
  rather than baking into the image.
- Update `docs/models_guideline.md` §3 and `docs/modules/llm.md` §1 for the new
  fields, and correct the "16 GB fits one" line in `manager.py`'s docstring.
- Remove the transformers/bitsandbytes narrative from both docs — §4 of `llm.md`
  describes `BitsAndBytesConfig` and the `AutoModelForImageTextToText` fallback,
  neither of which will exist.

---

At this point the 27B runs as a better chat model on a leaner stack. Phases 4-6
unlock the new capabilities — each independent, so they can be reordered or dropped.

### Phase 4 — Reasoning controls (cheapest)

Pure passthrough. Today `manager.stream(..., **_)` **silently swallows** anything
unrecognised, so a client sending `reasoning_effort` gets no error and no effect.

- `schemas.py`: promote `reasoning_effort` and `preserve_thinking` to named,
  validated fields (`Literal["low","medium","xhigh"]`) — a bad value should 422.
- `manager._prepare()`: forward both into `apply_chat_template`.
- **Replace `**_` with explicit kwargs** so unknown params raise instead of vanishing.
- Default from `default_reasoning_effort` when the request omits it.

**Also flip the thinking default.** [manager.py:219](models/app/modules/llm/manager.py#L219)
defaults `enable_thinking=False`; Qwen3.8 ships thinking **on**.

### Phase 5 — Tool calling (highest value; aligns with Curator)

Qwen3.8 emits XML, not JSON:

```
<tool_call>
<function=get_weather>
<parameter=city>Hanoi</parameter>
</function>
</tool_call>
```

1. **`schemas.py`** — add `tools` / `tool_choice`; `ChatMessage` gains
   `tool_call_id` and `name` so `role: "tool"` results can be sent back.
2. **`manager._prepare()`** — pass `tools=` into `apply_chat_template`.
3. **`toolcalls.py`** — parse the XML into OpenAI `tool_calls`. The template
   states the model may emit prose **before** a call but not after, which makes
   the split unambiguous.
4. **Streaming is the hard part.** A half-emitted `<tool_call>` is meaningless: the
   stream must detect the opening tag, stop forwarding text, buffer to
   `</tool_call>`, then emit one structured delta. This is a **third stream mode**
   alongside `thinking`/`text` — extend `CloseStripper`'s buffering idea rather
   than inventing a parallel mechanism.
5. **`service.py`** — emit standard `delta.tool_calls`, set
   `finish_reason: "tool_calls"` (per §5b).

> Sequence this **with** the Curator backend work. The MCP module owns tool
> *schemas* and *execution*; this phase only makes the model able to request a
> call. Building either half blind to the other produces a seam that doesn't fit.

### Phase 6 — Vision (gated on spike item 4)

- **`schemas.py`** — `ChatMessage.content` becomes `str | List[ContentPart]`
  (`{type: "text"}` / `{type: "image_url"}` / `{type: "video_url"}`). Breaking
  change; the `str` form must keep working.
- **`content.py`** — normalise parts, decode `data:` URIs, fetch/size-limit images.
- **Validate**: the chat template *raises* if a system message contains an image.
  Return 422, not a Jinja traceback.
- **`n_ctx` pressure**: images consume a large token budget each. Revisit the
  `n_ctx` number here — don't assume the text-tuned value survives.
- **Lector tie-in**: this is what enables OCR / translation / description of manga
  pages. Confirm the `read` module wants it before paying the cost.

### Not planned: MTP (Multi-Token Prediction)

`mtp_num_hidden_layers: 1` enables speculative decoding for free speed, but engine
support is immature. Nothing here blocks adding it later.

---

## 7. Sequencing warning

You are making **three** changes at once:

1. transformers/bnb → llama.cpp/GGUF (engine)
2. Qwen3.5-9B → Qwen3.8-27B (model)
3. Deleting the old path entirely (no fallback)

Phases 1-2 deliberately separate (3) from (1) and (2): **replace, verify, then
delete.** If you delete first and llama.cpp misbehaves, you have no working
service and no quick way back except git.

The one thing you cannot separate is (1) from (2) — Qwen3.5-9B has no reason to
run on llama.cpp, and Qwen3.8-27B can't run well on transformers. If quality
regresses after Phase 1, that ambiguity is the cost of the decision; budget a
little time to A/B against the old branch before deleting it.

---

## 8. Cross-module impact

`CLAUDE.md`: *"A feature added to one module usually needs a matching change in the
others."* Phases 0-3 are contained within `models/`. **Phases 4-6 are not.**

| Phase | `models` | `backend` | `frontend` | `supabase` |
|---|---|---|---|---|
| 0-3 engine swap | ✅ all of it | — | — | — |
| 4 reasoning | new fields | pass `reasoning_effort` through | optional depth selector | — |
| **5b contract** | `text`→`content`, `thinking`→`reasoning_content` | SDK parses natively (simplifies) | **breaking** — SSE reader must change | — |
| 5 tools | emit `tool_calls` | Curator: schemas + execution + loop | render calls/results in chat | `mcp_tool_calls` ✅ *already migrated* |
| 6 vision | accept image parts | upload → storage → data URI | image upload in composer | reuse `read` bucket? |

Two things worth noticing:

- **`supabase/migrations/20260725143632_add_mcp_tool_calls.sql` already exists.**
  The persistence layer for Phase 5 is ahead of the model layer — read that schema
  before designing the `tool_calls` response shape so they agree.
- **§5b is the only backward-incompatible change to an existing, working feature.**
  Everything else is additive. It needs a frontend change in the same PR.

---

## 9. Open questions

- ~~**Does `enable_thinking` survive the GGUF chat template?**~~ ✅ **Resolved by
  Tier 0.** Renders `<|im_start|>assistant\n<think>\n` — the two-phase prefill works.
- ~~**Does `transformers` stay as a tokenizer-only dependency?**~~ ✅ **Resolved by
  Tier 0 — it goes entirely.** `jinja2` renders the GGUF-embedded template.
- **Does `reasoning_effort` fight the two-phase flow?** It injects instructions into
  the *system prompt*; `ThinkingBudgetProcessor` clamps at the *token* level. At
  `xhigh` they work against each other. Test whether `reasoning_effort: "low"` alone
  achieves what the custom processor was built for — if so, that's more bespoke code
  you can retire.
- ~~**Q4 with offload, or Q3 fully resident?**~~ ✅ **Resolved — Q3 wins, 2.4×**
  (25.0 vs 10.5 tok/s), with reasoning and tool-calling quality intact. Higher
  bit-width lost because fitting in VRAM matters more than precision here.
