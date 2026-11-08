"""Make the pip-installed CUDA runtime loadable before `llama_cpp` is imported.

The prebuilt llama-cpp-python wheel ships `ggml-cuda.dll` but *not* the CUDA
runtime it links against. While torch was a dependency it pulled that runtime in
as a side effect; now that torch is gone, nothing does — and the failure surfaces
as `Failed to load shared library 'llama.dll'`, which names the wrong file and is
genuinely confusing to debug.

`os.add_dll_directory()` alone is **not** sufficient: Windows does not reliably
search user directories when resolving a *transitive* dependency of a
ctypes-loaded DLL. The runtime must be preloaded by absolute path so it is
already resident in the process by the time llama.dll asks for it.

Import and call `bootstrap()` before importing llama_cpp. A no-op off Windows,
where the loader follows RPATH from the nvidia wheels correctly.
"""
from __future__ import annotations

import ctypes
import glob
import logging
import os
import sys

logger = logging.getLogger(__name__)

# cublas depends on cublasLt, so load order matters here.
_RUNTIME_PATTERNS = ("cudart64_*.dll", "cublasLt64_*.dll", "cublas64_*.dll")


def bootstrap() -> list[str]:
    """Preload the CUDA runtime DLLs. Returns the basenames actually loaded."""
    if sys.platform != "win32":
        return []

    roots = glob.glob(
        os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")
    )
    if not roots:
        logger.warning(
            "No nvidia/*/bin directories found — is nvidia-cuda-runtime-cu12 "
            "installed? llama_cpp will fail to load its CUDA backend."
        )
        return []

    for root in roots:
        os.add_dll_directory(root)

    loaded: list[str] = []
    for pattern in _RUNTIME_PATTERNS:
        for root in roots:
            for path in glob.glob(os.path.join(root, pattern)):
                try:
                    ctypes.CDLL(path)
                    loaded.append(os.path.basename(path))
                except OSError:
                    logger.debug("Could not preload %s", path, exc_info=True)

    logger.info("CUDA runtime preloaded: %s", loaded or "nothing")
    return loaded
