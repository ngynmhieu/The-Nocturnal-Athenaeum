"""Paste the reference page's lettering onto the target page.

Detection runs on grayscale, compositing on the BGR images. Only pixels under the
(feathered) text mask change; everywhere else the target stays byte-identical.
"""
from __future__ import annotations

import cv2
import numpy as np

from .align import align
from .errors import TranslateRefusal
from .regions import match_tone, text_mask

_NOTHING_TO_TRANSLATE = "Nothing to translate: these pages have the same text."


def _to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def translate_by_reference(target_bgr: np.ndarray, reference_bgr: np.ndarray) -> np.ndarray:
    """Return `target_bgr` with the reference's text composited into its bubbles."""
    h, w = target_bgr.shape[:2]
    alignment = align(_to_gray(reference_bgr), _to_gray(target_bgr))

    def warp(img: np.ndarray, border) -> np.ndarray:
        return cv2.warpAffine(img, alignment.matrix, (w, h), flags=cv2.INTER_AREA,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=border)

    warped = warp(reference_bgr, (255, 255, 255))
    covered = warp(np.full(reference_bgr.shape[:2], 255, np.uint8), 0) >= 250

    tgt_gray, ref_gray = _to_gray(target_bgr), _to_gray(warped)
    mask = text_mask(ref_gray, tgt_gray, covered)
    if not mask.any():
        raise TranslateRefusal(_NOTHING_TO_TRANSLATE)

    lut = match_tone(ref_gray, tgt_gray, covered)
    toned = cv2.LUT(warped, lut)  # same LUT on every channel

    alpha = cv2.dilate(mask, np.ones((5, 5), np.uint8)).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (7, 7), 0)
    if target_bgr.ndim == 3:
        alpha = alpha[..., None]
    blended = target_bgr * (1 - alpha) + toned * alpha
    out = target_bgr.copy()
    changed = (alpha > 0).reshape(h, w)
    out[changed] = np.clip(np.rint(blended), 0, 255).astype(np.uint8)[changed]
    return out
