"""Decide which pixels of an aligned reference page are lettering.

Pure OpenCV, no I/O. Every size threshold is tuned at 1024 px page height and
scaled by `k = height / 1024`; an unscaled version mistook edited art for text on
2x pages. Detection is deliberately conservative: a missed bubble is visible and
fixable, art from the other edition leaking in is not.
"""
from __future__ import annotations

from typing import Protocol

import cv2
import numpy as np

_DIFF_THRESHOLD = 45  # on 3x3-blurred images
_DARK = 110  # glyph ink
_PAPER = 200  # bubble paper
_MIN_GLYPHS_REF = 4
_MIN_GLYPHS_TGT = 2
_MIN_INK_ON_PAPER = 0.8
_MIN_TONE_SAMPLES = 30
_MIN_MEDIAN_GLYPH = 10  # k^2 px: halftone dots are a few px; real letters (even furigana) are not
_MIN_TARGET_PAPER = 0.7  # lettering sits in a bubble: the target group is mostly paper-white
_FAINT_DIFF = 20  # ink inside a text group only has to differ this much to be replaced
_INK_MAX = 200  # darker than this counts as ink (furigana strokes are thin and grey)


class TextClassifier(Protocol):
    """Decides whether one changed group is lettering (the seam for a future detector)."""

    def is_text(self, region: np.ndarray, ref_gray: np.ndarray, tgt_gray: np.ndarray,
                scale: float) -> bool:
        """`region` is a bool mask of the group; the grays are the matching crops."""
        ...


def _glyph_areas(gray: np.ndarray, region: np.ndarray, scale: float) -> np.ndarray:
    dark = ((gray < _DARK) & region).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    areas = stats[1:n, cv2.CC_STAT_AREA]
    return areas[(areas >= 3 * scale**2) & (areas <= 400 * scale**2)]


class GlyphHeuristic:
    """Lettering is a cluster of letter-sized dark glyphs on bubble paper."""

    def is_text(self, region: np.ndarray, ref_gray: np.ndarray, tgt_gray: np.ndarray,
                scale: float) -> bool:
        ref_glyphs = _glyph_areas(ref_gray, region, scale)
        if len(ref_glyphs) < _MIN_GLYPHS_REF:
            return False
        if len(_glyph_areas(tgt_gray, region, scale)) < _MIN_GLYPHS_TGT:
            return False
        px = ref_gray[region]
        if float(np.mean((px > _PAPER) | (px < _DARK))) <= _MIN_INK_ON_PAPER:
            return False
        # Screentone: the edition's edited art is covered in halftone dots, which pass the
        # tests above as "glyphs". Dots are tiny, and they sit on art, not on bubble paper.
        if float(np.median(ref_glyphs)) < _MIN_MEDIAN_GLYPH * scale**2:
            return False
        return float(np.mean(tgt_gray[region] > _PAPER)) >= _MIN_TARGET_PAPER


def match_tone(reference_gray_warped: np.ndarray, target_gray: np.ndarray,
               covered: np.ndarray) -> np.ndarray:
    """uint8 LUT mapping reference grey levels to the target's printing tone."""
    ref = cv2.GaussianBlur(reference_gray_warped, (5, 5), 0)
    tgt = cv2.GaussianBlur(target_gray, (5, 5), 0)
    lut = np.arange(256, dtype=np.uint8)
    for level in range(256):
        sel = covered & (ref == level)
        if int(sel.sum()) > _MIN_TONE_SAMPLES:
            lut[level] = int(np.median(tgt[sel]))
    return np.maximum.accumulate(lut)


def text_mask(ref_gray: np.ndarray, tgt_gray: np.ndarray, covered: np.ndarray,
              classifier: TextClassifier | None = None) -> np.ndarray:
    """uint8 0/1 mask (target size) of the changed groups the classifier calls lettering."""
    classifier = classifier or GlyphHeuristic()
    k = tgt_gray.shape[0] / 1024
    ref_b = cv2.GaussianBlur(ref_gray, (3, 3), 0)
    tgt_b = cv2.GaussianBlur(tgt_gray, (3, 3), 0)

    diff = ((cv2.absdiff(ref_b, tgt_b) > _DIFF_THRESHOLD) & covered).astype(np.uint8)
    size = max(1, int(2 * k))
    diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    group_kernel = np.ones((int(13 * k) | 1,) * 2, np.uint8)
    groups = cv2.dilate(diff, group_kernel)

    accepted = np.zeros(tgt_gray.shape, np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(groups, connectivity=8)
    for i in range(1, n):
        x, y = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        region = labels[y:y + h, x:x + w] == i
        if classifier.is_text(region, ref_gray[y:y + h, x:x + w], tgt_gray[y:y + h, x:x + w], k):
            accepted[y:y + h, x:x + w][region] = 1
    # Eroding the grouped blobs back (a morphological closing of the changed pixels)
    # keeps the gaps between glyphs filled without growing the mask past the lettering.
    mask = cv2.erode(accepted, group_kernel)
    # The open above drops thin strokes (furigana) and the threshold drops faint ones,
    # so pick up remaining ink that differs from the reference, but only inside
    # groups already accepted as text: this never reaches into surrounding art.
    # Unblurred: blurring washes a 1 px grey stroke out of the ink range. The reference
    # must be paper there: furigana sits on bubble paper, whereas a mismatch against
    # the reference's own art is just misregistration, not lettering.
    faint = (cv2.absdiff(ref_gray, tgt_gray) > _FAINT_DIFF) & (tgt_gray < _INK_MAX) & (ref_gray > _PAPER)
    # Only glyph-sized specks: a long connected ink run is art, not lettering.
    wanted = (accepted.astype(bool) & faint).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(wanted, connectivity=8)
    small = np.flatnonzero(stats[:, cv2.CC_STAT_AREA] <= 400 * k**2)
    mask |= (np.isin(labels, small[small > 0])).astype(np.uint8)
    return mask & covered.astype(np.uint8)
