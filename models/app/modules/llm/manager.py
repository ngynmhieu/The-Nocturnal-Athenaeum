"""LLM model lifecycle and inference, backed by llama.cpp.

Keeps one model resident, loads/unloads/swaps on demand, and runs the two-phase
(thinking -> answer) generation. Configuration lives in config.py and the
decoding helpers in processors.py; everything that needs the live model lives here.

Two-phase flow (when thinking is enabled):
  Phase 1 — generate the <think> block, capped at max_thinking_tokens, stopping at
            </think>. ThinkingBudgetProcessor nudges it to close before the cap.
  Phase 2 — generate the answer from the closed prompt, with its own full budget.

Phase 2 continues from a *string*: the phase-1 prompt plus the reasoning plus a
closing tag. The transformers engine this replaced had to concatenate token
tensors instead, which is why torch appeared here at all.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

import jinja2

from . import cuda_bootstrap

# Must precede the llama_cpp import: the wheel's CUDA backend links a runtime
# that Windows will not otherwise find. See cuda_bootstrap for the details.
cuda_bootstrap.bootstrap()

from llama_cpp import Llama, LogitsProcessorList  # noqa: E402

from .config import ModelConfig, load_catalog  # noqa: E402
from .processors import (  # noqa: E402
    THINK_CLOSE,
    CloseStripper,
    ThinkingBudgetProcessor,
)

logger = logging.getLogger(__name__)

MessageDict = Dict[str, object]


@dataclass(frozen=True)
class GenerateResult:
    """Structured output from generate() — thinking and text as separate fields."""
    thinking: str  # empty when thinking was disabled or model skipped <think>
    text: str


def _template_env() -> jinja2.Environment:
    """Jinja environment matching what chat templates expect.

    Qwen's template calls raise_exception() for invalid input (e.g. an image in a
    system message), so that global has to exist or rendering dies with a confusing
    'raise_exception is undefined' instead of the intended message.
    """
    def raise_exception(message: str):
        raise jinja2.exceptions.TemplateError(message)

    env = jinja2.Environment()
    env.globals["raise_exception"] = raise_exception
    return env


class LlmManager:
    def __init__(self) -> None:
        self._catalog: Dict[str, ModelConfig] = load_catalog()
        self._config: Optional[ModelConfig] = None
        self.model: Optional[Llama] = None
        self._template: Optional[jinja2.Template] = None
        self._close_token_id: Optional[int] = None  # first token of </think>
        # Serializes every use of the model: swaps and generations. A llama.cpp
        # context holds one KV cache and is not thread-safe, and FastAPI runs each
        # request on its own threadpool thread. A plain Lock (not RLock) on purpose:
        # a stream is consumed across threadpool threads, and Lock may be released
        # by a different thread than the one that acquired it.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Catalog
    # ------------------------------------------------------------------ #

    def list_configs(self) -> List[ModelConfig]:
        return list(self._catalog.values())

    def default_id(self) -> Optional[str]:
        for cfg in self._catalog.values():
            if cfg.default:
                return cfg.id
        return next(iter(self._catalog), None)  # fall back to first if none marked

    @property
    def current_model_id(self) -> Optional[str]:
        return self._config.id if self._config else None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def ensure(self, model_id: str) -> None:
        """Make `model_id` the resident model, swapping out the current one."""
        with self._lock:
            if model_id not in self._catalog:
                raise KeyError(model_id)
            if self._config and self._config.id == model_id:
                return
            if self.model is not None:
                self._unload_locked()
            self._load_locked(self._catalog[model_id])

    def load_default(self) -> None:
        model_id = self.default_id()
        if model_id:
            self.ensure(model_id)

    def unload(self) -> None:
        with self._lock:
            self._unload_locked()

    def _load_locked(self, cfg: ModelConfig) -> None:
        logger.info("Loading %s (%s) ...", cfg.id, cfg.gguf_file)
        self.model = Llama.from_pretrained(
            repo_id=cfg.hf_repo,
            filename=cfg.gguf_file,
            n_gpu_layers=cfg.n_gpu_layers,
            n_ctx=cfg.n_ctx,
            verbose=False,
        )
        self._config = cfg

        # The chat template ships inside the GGUF, so there is no tokenizer repo
        # to fetch and no transformers dependency to carry.
        template_src = self.model.metadata.get("tokenizer.chat_template")
        if not template_src:
            raise RuntimeError(
                f"{cfg.gguf_file} has no tokenizer.chat_template in its metadata; "
                "cannot format prompts."
            )
        self._template = _template_env().from_string(template_src)

        close_ids = self.model.tokenize(THINK_CLOSE.encode(), add_bos=False)
        self._close_token_id = int(close_ids[0]) if close_ids else None

    def _unload_locked(self) -> None:
        if self.model is not None:
            self.model.close()
        self.model = None
        self._template = None
        self._config = None
        self._close_token_id = None

    def warmup(self) -> None:
        """Force the one-time CUDA PTX->SASS compile before serving traffic.

        The prebuilt wheel ships kernels as PTX, so the driver JIT-compiles them on
        first use for the local GPU architecture. That compile is slow enough to be
        mistaken for a broken deployment, and without this it lands on whoever sends
        the first request. Results persist in the driver's compute cache.
        """
        if self.model is None:
            return
        logger.info("Warming up (compiling CUDA kernels) ...")
        self.model("hi", max_tokens=1, temperature=0.0)
        self.model.reset()
        logger.info("Warm.")

    # ------------------------------------------------------------------ #
    # Inference — setup helpers
    # ------------------------------------------------------------------ #

    def _thinking(self, enable_thinking: bool) -> bool:
        return bool(enable_thinking) and bool(
            self._config and self._config.supports_thinking)

    def _render(self, messages: List[MessageDict], *, enable_thinking: bool,
                reasoning_effort: Optional[str] = None,
                tools: Optional[list] = None, **extra) -> str:
        """Render messages to a prompt string via the GGUF's own chat template."""
        return self._template.render(
            messages=messages,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort or self._config.default_reasoning_effort,
            tools=tools,
            **extra,
        )

    def _fit(self, messages: List[MessageDict], *, reserve: int,
             enable_thinking: bool, reasoning_effort: Optional[str],
             tools: Optional[list]) -> str:
        """Render the prompt, dropping the oldest turns until it fits the context.

        llama.cpp refuses a prompt that doesn't fit n_ctx, and callers send the
        whole conversation. `reserve` keeps room for the tokens still to be
        generated. System messages and the final message are always kept, and a
        dropped turn takes its replies with it so history still opens on a user.
        """
        budget = self._config.n_ctx - reserve
        kept = list(messages)
        while True:
            prompt = self._render(kept, enable_thinking=enable_thinking,
                                  reasoning_effort=reasoning_effort, tools=tools)
            n_tokens = len(self.model.tokenize(prompt.encode("utf-8"), special=True))
            if n_tokens <= budget:
                if len(kept) < len(messages):
                    logger.info("Dropped %d oldest messages to fit n_ctx=%d.",
                                len(messages) - len(kept), self._config.n_ctx)
                return prompt
            oldest = next((i for i, m in enumerate(kept[:-1])
                           if m.get("role") != "system"), None)
            if oldest is None:
                raise ValueError(
                    f"Prompt needs {n_tokens} tokens but only {budget} of the "
                    f"{self._config.n_ctx}-token context are left after reserving "
                    f"{reserve} for the reply.")
            del kept[oldest]
            while oldest < len(kept) - 1 and kept[oldest].get("role") not in ("user", "system"):
                del kept[oldest]

    def _sampling_kwargs(self) -> dict:
        """generate() kwargs for the configured sampler (empty -> llama.cpp defaults)."""
        s = self._config.sampling
        if s is None:
            return {"temperature": 0.0}
        return dict(
            temperature=s.temperature,
            top_p=s.top_p,
            top_k=s.top_k,
            min_p=s.min_p,
            presence_penalty=s.presence_penalty,
        )

    def _budget_processors(self, budget: int) -> Optional[LogitsProcessorList]:
        """Phase-1 logits processors: ramp </think> as the budget runs low.

        Stateful, so this must be rebuilt for every generation call.
        """
        if self._close_token_id is None:
            return None
        return LogitsProcessorList(
            [ThinkingBudgetProcessor(self._close_token_id, budget)]
        )

    def _close_thinking(self, prompt: str, thinking: str, closed: bool) -> str:
        """Build the phase-2 prompt, force-closing an over-budget thought.

        `closed` is True when phase 1 ended on the </think> stop-string rather than
        the token cap. The stop-string is swallowed from the output, so the tag can
        never be detected in `thinking` and always has to be re-added; if the model
        never closed, the configured wrap-up message goes in instead so the thought
        lands gracefully.
        """
        if closed:
            return prompt + thinking + THINK_CLOSE + "\n\n"
        return prompt + thinking + self._config.thinking_budget_message

    # ------------------------------------------------------------------ #
    # Inference — entry points
    # ------------------------------------------------------------------ #

    def generate(self, messages: List[MessageDict], max_new_tokens: int | None = None,
                 *, enable_thinking: bool = True,
                 reasoning_effort: Optional[str] = None,
                 tools: Optional[list] = None) -> GenerateResult:
        with self._lock:
            return self._generate_locked(messages, max_new_tokens,
                                         enable_thinking=enable_thinking,
                                         reasoning_effort=reasoning_effort, tools=tools)

    def stream(self, messages: List[MessageDict], max_new_tokens: int | None = None,
               *, enable_thinking: bool = True,
               reasoning_effort: Optional[str] = None,
               tools: Optional[list] = None) -> Iterator[Tuple[str, str]]:
        # Held from the first chunk until the stream is exhausted or closed; a
        # client disconnect closes the generator, which releases the lock.
        with self._lock:
            yield from self._stream_locked(messages, max_new_tokens,
                                           enable_thinking=enable_thinking,
                                           reasoning_effort=reasoning_effort, tools=tools)

    def _prepare(self, messages: List[MessageDict], max_new_tokens: Optional[int], *,
                 enable_thinking: bool, reasoning_effort: Optional[str],
                 tools: Optional[list]) -> Tuple[bool, int, str]:
        """Resolve thinking + answer budget and render a prompt that fits n_ctx."""
        enable_thinking = self._thinking(enable_thinking)
        answer_budget = max_new_tokens or self._config.max_new_tokens
        # Phase 2 continues from phase 1's prompt, so thinking (plus the wrap-up
        # message, ~32 tokens) must fit alongside the answer.
        reserve = answer_budget + (self._config.max_thinking_tokens + 32
                                   if enable_thinking else 0)
        prompt = self._fit(messages, reserve=reserve, enable_thinking=enable_thinking,
                           reasoning_effort=reasoning_effort, tools=tools)
        return enable_thinking, answer_budget, prompt

    def _generate_locked(self, messages: List[MessageDict], max_new_tokens: int | None,
                         **opts) -> GenerateResult:
        enable_thinking, answer_budget, prompt = self._prepare(
            messages, max_new_tokens, **opts)
        sampling = self._sampling_kwargs()

        if not enable_thinking:
            out = self.model(prompt, max_tokens=answer_budget, **sampling)
            return GenerateResult(thinking="", text=out["choices"][0]["text"].strip("\n"))

        # Phase 1 — thinking, capped at its own budget, stopping at </think>.
        think_budget = self._config.max_thinking_tokens
        out1 = self.model(
            prompt, max_tokens=think_budget, stop=[THINK_CLOSE],
            logits_processor=self._budget_processors(think_budget), **sampling,
        )
        thinking = out1["choices"][0]["text"]
        closed = out1["choices"][0]["finish_reason"] == "stop"

        # Phase 2 — the answer, with its own full budget.
        out2 = self.model(
            self._close_thinking(prompt, thinking, closed),
            max_tokens=answer_budget, **sampling,
        )
        return GenerateResult(
            thinking=thinking.strip(),
            text=out2["choices"][0]["text"].strip("\n"),
        )

    def _stream_locked(self, messages: List[MessageDict], max_new_tokens: int | None,
                       **opts) -> Iterator[Tuple[str, str]]:
        enable_thinking, answer_budget, prompt = self._prepare(
            messages, max_new_tokens, **opts)
        sampling = self._sampling_kwargs()

        if not enable_thinking:
            for ev in self.model(prompt, max_tokens=answer_budget,
                                 stream=True, **sampling):
                chunk = ev["choices"][0]["text"]
                if chunk:
                    yield ("text", chunk)
            return

        # Phase 1 — thinking; tag every chunk "thinking" and strip a trailing tag.
        think_budget = self._config.max_thinking_tokens
        stripper = CloseStripper()
        thinking_parts: List[str] = []
        closed = False
        for ev in self.model(
            prompt, max_tokens=think_budget, stop=[THINK_CLOSE], stream=True,
            logits_processor=self._budget_processors(think_budget), **sampling,
        ):
            if ev["choices"][0].get("finish_reason") == "stop":
                closed = True
            chunk = ev["choices"][0]["text"]
            if not chunk:
                continue
            thinking_parts.append(chunk)
            for piece in stripper.feed(chunk):
                yield ("thinking", piece)
        for piece in stripper.flush():
            yield ("thinking", piece)

        # Phase 2 — the answer, with its own full budget; tag every chunk "text".
        prompt2 = self._close_thinking(prompt, "".join(thinking_parts), closed)
        for ev in self.model(prompt2, max_tokens=answer_budget,
                             stream=True, **sampling):
            chunk = ev["choices"][0]["text"]
            if chunk:
                yield ("text", chunk)


# Module-level singleton — one resident model for the service.
manager = LlmManager()
