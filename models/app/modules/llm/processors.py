"""Generation-shaping helpers for the two-phase (thinking → answer) flow.

  - ThinkingBudgetProcessor: nudges the model toward </think> as the budget runs low.
  - CloseStripper: drops a trailing </think> out of the streamed thinking text.

The presence penalty that used to live here is gone: transformers had no native
one, which is why it was hand-written, but llama.cpp applies presence_penalty
itself. It is now a plain sampling field on SamplingConfig.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
import numpy.typing as npt

THINK_CLOSE = "</think>"


class ThinkingBudgetProcessor:
    """Gradually guides the model toward </think> as the thinking budget runs low.

    From warn_start (75% of budget) to the hard limit, the first token of </think>
    gets a linearly increasing boost — peaking at max_boost at the limit. This makes
    the model naturally wrap up its thought and emit </think> on its own terms, rather
    than being cut off mid-sentence by a hard stop. The stop-string still fires when
    the tag appears, so this only shifts *when* that happens.

    Only the first token of </think> is boosted. Once the model commits to it, the KV
    cache makes the rest of the sequence very likely by continuation.

    llama.cpp hands each processor a 1-D float array of the full vocabulary — unlike
    transformers, which passed a batched 2-D tensor. The processor is stateful
    (it counts tokens), so build a fresh one per generation call.
    """
    def __init__(self, close_token_id: int, budget: int,
                 warn_start: float = 0.75, max_boost: float = 15.0) -> None:
        self._close_id = close_token_id
        self._warn_at = int(budget * warn_start)
        self._remaining = budget - self._warn_at
        self._max_boost = max_boost
        self._count = 0

    def __call__(self, input_ids: npt.NDArray[np.intc],
                 scores: npt.NDArray[np.single]) -> npt.NDArray[np.single]:
        self._count += 1
        if self._count <= self._warn_at:
            return scores
        progress = min((self._count - self._warn_at) / max(self._remaining, 1), 1.0)
        scores[self._close_id] += progress * self._max_boost
        return scores


class CloseStripper:
    """Strips a trailing </think> tag out of the thinking stream.

    The thinking phase generates with a stop-string on </think>, so the streamer
    may emit that tag before generation halts. This buffers just enough of the
    tail to drop the tag (and never leak a partial one mid-stream).
    """
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, chunk: str) -> Iterator[str]:
        self._buf += chunk
        if THINK_CLOSE in self._buf:
            head, _, _ = self._buf.partition(THINK_CLOSE)
            self._buf = ""
            if head:
                yield head
            return
        # Hold back a tail that could be the start of </think>.
        keep = len(THINK_CLOSE) - 1
        if len(self._buf) > keep:
            emit, self._buf = self._buf[:-keep], self._buf[-keep:]
            if emit:
                yield emit

    def flush(self) -> Iterator[str]:
        if THINK_CLOSE in self._buf:
            head, _, _ = self._buf.partition(THINK_CLOSE)
            self._buf = ""
            if head:
                yield head
        elif self._buf:
            yield self._buf
            self._buf = ""
