"""Qwen language model service - handles model loading and generation."""
from __future__ import annotations

from typing import Dict, Iterator, List, Optional
import threading
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TextIteratorStreamer


class QwenService:
    """Service for managing Qwen model loading and inference.
    
    This service is responsible for:
    - Loading tokenizer and model once on startup
    - Providing methods for both streaming and non-streaming generation
    - Managing model lifecycle (load, unload)
    """
    
    _instance: Optional["QwenService"] = None
    
    def __init__(self):
        """Initialize the service (model not loaded yet)."""
        self.tokenizer = None
        self.model = None
        self.model_name = None
        self.quantize = False
        self.is_loaded = False

    def _require_loaded(self) -> None:
        if not self.is_loaded or self.tokenizer is None or self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

    def _build_chat_input(self, messages: List[Dict[str, str]], enable_thinking: bool = False) -> str:
        """Build the prompt using the model chat template."""
        self._require_loaded()
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )

    def _prepare_model_inputs(self, messages: List[Dict[str, str]], enable_thinking: bool = False):
        """Tokenize the prompt and move tensors to the model device."""
        text = self._build_chat_input(messages, enable_thinking=enable_thinking)
        return self.tokenizer([text], return_tensors="pt").to(self.model.device)

    def _decode_answer(self, output_ids: List[int], enable_thinking: bool = False) -> str:
        """Decode generated token IDs into an assistant response."""
        if enable_thinking:
            try:
                # 151668 is </think> in the current Qwen template flow used by test.py.
                index = len(output_ids) - output_ids[::-1].index(151668)
            except ValueError:
                index = 0
            return self.tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

        return self.tokenizer.decode(output_ids, skip_special_tokens=True).strip("\n")
    
    @classmethod
    def get_instance(cls) -> "QwenService":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = QwenService()
        return cls._instance
    
    async def load(self, model_name: str, quantize: bool = False) -> None:
        """Load tokenizer and model asynchronously.
        
        Args:
            model_name: HuggingFace model identifier (e.g., "Qwen/Qwen3-14B")
            quantize: Whether to use 4-bit quantization (requires bitsandbytes)
            
        Raises:
            RuntimeError: If model loading fails
        """
        self.model_name = model_name
        self.quantize = quantize

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        if quantize:
            try:
                import bitsandbytes  # noqa: F401
            except Exception as exc:
                raise RuntimeError(
                    "bitsandbytes is required for quantized loading. Install it before starting the server."
                ) from exc

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype="auto",
                device_map="auto",
                trust_remote_code=True,
            )

        self.is_loaded = True
    
    def generate_once(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> tuple[str, float]:
        """Generate a single response (non-streaming).
        
        Args:
            messages: Chat history with role and content
            max_new_tokens: Maximum tokens to generate
            enable_thinking: Enable extended thinking mode
            
        Returns:
            Tuple of (generated_text, elapsed_time_in_seconds)
            
        Raises:
            RuntimeError: If model not loaded
        """
        self._require_loaded()

        model_inputs = self._prepare_model_inputs(messages, enable_thinking=enable_thinking)
        start_time = time.time()
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=max_new_tokens,
        )
        elapsed = time.time() - start_time

        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        answer = self._decode_answer(output_ids, enable_thinking=enable_thinking)
        return answer, elapsed
    
    def stream_generate(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> Iterator[str]:
        """Stream tokens as they are generated.
        
        Args:
            messages: Chat history with role and content
            max_new_tokens: Maximum tokens to generate
            enable_thinking: Enable extended thinking mode
            
        Yields:
            Individual tokens or chunks as they are generated
            
        Raises:
            RuntimeError: If model not loaded
        """
        self._require_loaded()

        model_inputs = self._prepare_model_inputs(messages, enable_thinking=enable_thinking)
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        generation_kwargs = dict(
            **model_inputs,
            max_new_tokens=max_new_tokens,
            streamer=streamer,
        )

        generation_error: list[BaseException | None] = [None]

        def _generate() -> None:
            try:
                self.model.generate(**generation_kwargs)
            except BaseException as exc:  # pragma: no cover - surfaced after streaming
                generation_error[0] = exc

        start_time = time.time()
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()

        for chunk in streamer:
            yield chunk

        thread.join()
        elapsed = time.time() - start_time

        if generation_error[0] is not None:
            raise generation_error[0]

        # The elapsed time is intentionally measured here even though the method
        # yields chunks. The caller can ignore it for now; it is kept for parity
        # with the non-streaming path and future telemetry hooks.
        _ = elapsed
    
    async def close(self) -> None:
        """Unload model and free resources.
        
        Call this during application shutdown.
        """
        if self.model is not None:
            del self.model
        if self.tokenizer is not None:
            del self.tokenizer

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self.model = None
        self.tokenizer = None
        self.model_name = None
        self.quantize = False
        self.is_loaded = False
    
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self.is_loaded
