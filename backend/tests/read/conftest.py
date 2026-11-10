"""Synthetic manga pages for the translate-by-reference tests.

Never commit real manga pages as fixtures: everything here is generated from seeded
RNGs, so the images are deterministic and the tests are not flaky.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

SCALE = 1.84  # the English reference is ~1.84x the Japanese target
SHIFT_X = 40  # some real pairs are offset horizontally by about this much
PAD = 8  # bubble boxes are padded by this many px (target coordinates)

# (centre x, centre y, half-width, half-height) as fractions of the page.
_BUBBLE_LAYOUT = [
    (0.30, 0.18, 0.20, 0.07),
    (0.70, 0.50, 0.20, 0.07),
    (0.35, 0.82, 0.20, 0.07),
]

# Edited-art patch in the reference, as fractions of the reference page (before the shift).
EDITED_PATCH = (0.55, 0.28, 0.85, 0.36)


def edited_patch_box(h: int = 1024, w: int = 610) -> tuple[int, int, int, int]:
    """The edited-art patch as `(x0, y0, x1, y1)` in target coordinates."""
    fx0, fy0, fx1, fy1 = EDITED_PATCH
    rw, rh = round(w * SCALE), round(h * SCALE)
    return (round((rw * fx0 + SHIFT_X) / SCALE), round(rh * fy0 / SCALE),
            round((rw * fx1 + SHIFT_X) / SCALE), round(rh * fy1 / SCALE))

_FURIGANA_TEXT, _FURIGANA_SCALE = "ri", 0.3  # tiny, thin ruby-like marks
_FURIGANA_OFFSET = (-40, -8)  # from the bubble centre, tucked against the lettering
_FURIGANA_INK = (150, 150, 150)  # light grey: weak enough to fall under the diff threshold


def furigana_boxes(h: int = 1024, w: int = 610) -> list[tuple[int, int, int, int]]:
    """Boxes `(x0, y0, x1, y1)` of the target's furigana-like marks, one per bubble."""
    (tw, th), base = cv2.getTextSize(_FURIGANA_TEXT, cv2.FONT_HERSHEY_SIMPLEX, _FURIGANA_SCALE, 1)
    boxes = []
    for fx, fy, _, _ in _BUBBLE_LAYOUT:
        x, y = int(fx * w) + _FURIGANA_OFFSET[0], int(fy * h) + _FURIGANA_OFFSET[1]
        boxes.append((x - 1, y - th - 1, x + tw + 1, y + base + 1))
    return boxes


def _draw_screentone(img: np.ndarray, box: tuple[int, int, int, int]) -> None:
    """The English edition's edited area: light grey covered in regular halftone dots."""
    x0, y0, x1, y1 = box
    cv2.rectangle(img, (x0, y0), (x1, y1), (225, 225, 225), -1)
    for y in range(y0 + 4, y1 - 2, 8):
        for x in range(x0 + 4, x1 - 2, 8):
            cv2.circle(img, (x, y), 2, (40, 40, 40), -1)


def _draw_line_art(img: np.ndarray, box: tuple[int, int, int, int]) -> None:
    """A few bold strokes and curves of the Japanese line art inside the edited area."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    cv2.ellipse(img, (cx, cy), ((x1 - x0) // 3, (y1 - y0) // 3), 15, 20, 300, (30, 30, 30), 3)
    cv2.line(img, (x0 + 5, y0 + 5), (x1 - 5, cy), (30, 30, 30), 3)
    cv2.line(img, (x0 + 5, y1 - 5), (cx, y0 + 5), (60, 60, 60), 2)


def _art(seed: int, h: int, w: int, color: bool) -> np.ndarray:
    """Busy random line art: plenty of corners and edges so SIFT has features."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 245, np.uint8)

    def pen() -> tuple[int, int, int]:
        if color:  # saturated colours
            return tuple(int(c) for c in rng.choice([0, 128, 255], 3))
        g = int(rng.integers(0, 200))
        return (g, g, g)

    for _ in range(max(250, h * w // 1500)):  # outlines and filled blobs
        centre = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        thickness = -1 if rng.random() < 0.4 else 2
        cv2.circle(img, centre, int(rng.integers(3, 30)), pen(), thickness)
    for _ in range(max(400, h * w // 1000)):  # lines and hatching
        p = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        q = (p[0] + int(rng.integers(-60, 60)), p[1] + int(rng.integers(-60, 60)))
        cv2.line(img, p, q, pen(), int(rng.integers(1, 4)))
    return img


def _draw_bubbles(img: np.ndarray, text: list[str], text_scale: float = 1.0) -> None:
    """White ellipse bubbles (fractions of the page) with centred black text."""
    h, w = img.shape[:2]
    font_scale, thick = 1.1 * text_scale, max(1, round(2 * text_scale))
    for (fx, fy, fw, fh), line in zip(_BUBBLE_LAYOUT, text):
        c = (int(fx * w), int(fy * h))
        cv2.ellipse(img, c, (int(fw * w), int(fh * h)), 0, 0, 360, (255, 255, 255), -1)
        (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thick)
        cv2.putText(img, line, (c[0] - tw // 2, c[1] + th // 2), cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, (0, 0, 0), thick, cv2.LINE_AA)


def make_page(seed: int, h: int, w: int, bubble_text: list[str], color: bool = False) -> np.ndarray:
    """A BGR page: seeded busy art, then one white ellipse bubble per text entry."""
    img = _art(seed, h, w, color)
    _draw_bubbles(img, bubble_text)
    return img


def make_pair(color: bool = False):
    """Return `(target_bgr, reference_bgr, bubbles)` for one synthetic page.

    The target is 1024 tall with stand-in "Japanese" text (`"AAAA"`). The reference
    is the same art scaled x1.84 and shifted ~40 px, with different bubble text
    (`"HELLO THERE"`) and one grey patch of edited art outside the bubbles.
    `bubbles` are the bubble boxes `(x0, y0, x1, y1)` in target coordinates,
    padded by 8 px. `color=True` makes the art saturated colour.
    """
    h, w = 1024, 610
    art = _art(7, h, w, color)
    target = art.copy()
    _draw_bubbles(target, ["AAAA"] * 3)
    _draw_line_art(target, edited_patch_box(h, w))
    for x0, y0, _, y1 in furigana_boxes(h, w):  # present in the target only
        cv2.putText(target, _FURIGANA_TEXT, (x0 + 1, y1 - 1 - cv2.getTextSize(
            _FURIGANA_TEXT, cv2.FONT_HERSHEY_SIMPLEX, _FURIGANA_SCALE, 1)[1]),
            cv2.FONT_HERSHEY_SIMPLEX, _FURIGANA_SCALE, _FURIGANA_INK, 1, cv2.LINE_AA)

    rh, rw = round(h * SCALE), round(w * SCALE)
    ref = cv2.resize(art, (rw, rh), interpolation=cv2.INTER_CUBIC)
    _draw_bubbles(ref, ["HELLO THERE"] * 3, text_scale=SCALE)
    fx0, fy0, fx1, fy1 = EDITED_PATCH
    _draw_screentone(ref, (int(rw * fx0), int(rh * fy0), int(rw * fx1), int(rh * fy1)))
    ref = cv2.warpAffine(ref, np.float32([[1, 0, SHIFT_X], [0, 1, 0]]), (rw, rh),
                         borderValue=(245, 245, 245))

    bubbles = [
        (int((fx - fw) * w) - PAD, int((fy - fh) * h) - PAD,
         int((fx + fw) * w) + PAD, int((fy + fh) * h) + PAD)
        for fx, fy, fw, fh in _BUBBLE_LAYOUT
    ]
    return target, ref, bubbles


# Soft steam the English edition painted over the art, as (centre x, centre y, half-width,
# half-height) fractions of the page. It runs right up against bubble 3.
STEAM = (0.62, 0.84, 0.20, 0.10)
_SMALL_LETTERING = "MM..."  # bubble 2 of the steam pair: small letters plus tiny dots


def steam_box(h: int = 1024, w: int = 610) -> tuple[int, int, int, int]:
    """The steam cloud's bounding box `(x0, y0, x1, y1)`."""
    fx, fy, fw, fh = STEAM
    return int((fx - fw) * w), int((fy - fh) * h), int((fx + fw) * w), int((fy + fh) * h)


def _draw_steam(img: np.ndarray) -> None:
    """A soft, blurry white cloud over the art: no outline, no sharp edges."""
    h, w = img.shape[:2]
    fx, fy, fw, fh = STEAM
    cloud = np.zeros((h, w), np.float32)
    cv2.ellipse(cloud, (int(fx * w), int(fy * h)), (int(fw * w * 0.8), int(fh * h * 0.8)),
                0, 0, 360, 1.0, -1)
    cloud = cv2.GaussianBlur(cloud, (0, 0), sigmaX=fw * w * 0.25)[..., None]
    img[:] = (img * (1 - 0.9 * cloud) + 240 * 0.9 * cloud).astype(np.uint8)


def _draw_skin(img: np.ndarray) -> None:
    """Where the steam goes: pale skin with fine grey hatching and sweat drops, the
    kind of near-white art with letter-sized dark marks that the steam half-hides."""
    x0, y0, x1, y1 = steam_box(*img.shape[:2])
    cv2.rectangle(img, (x0, y0), (x1, y1), (238, 238, 238), -1)
    rng = np.random.default_rng(11)
    for _ in range(60):  # short hatch strokes
        x, y = int(rng.integers(x0, x1 - 20)), int(rng.integers(y0, y1 - 10))
        cv2.line(img, (x, y), (x + 14, y + 8), (120, 120, 120), 1, cv2.LINE_AA)
    for _ in range(60):  # sweat drops
        x, y = int(rng.integers(x0 + 5, x1 - 5)), int(rng.integers(y0 + 5, y1 - 5))
        cv2.ellipse(img, (x, y), (3, 5), 0, 0, 360, (30, 30, 30), 2, cv2.LINE_AA)


def _draw_small_lettering(img: np.ndarray, text: str) -> None:
    """Small text centred in bubble 2."""
    h, w = img.shape[:2]
    fx, fy, _, _ = _BUBBLE_LAYOUT[1]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.putText(img, text, (int(fx * w) - tw // 2, int(fy * h) + th // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)


def make_steam_grays():
    """Return already-aligned `(reference_gray, target_gray, bubbles)` of one page size.

    Same art on both, so the only differences are what the English edition changed:
    a soft steam cloud touching bubble 3, and the lettering. Bubble 2 holds small
    lettering on both sides (`"MM..."` in the reference), whose dots are far smaller
    than its letters. `bubbles` are the padded bubble boxes `(x0, y0, x1, y1)`.
    """
    h, w = 1024, 610
    art = _art(7, h, w, False)
    _draw_skin(art)
    target = art.copy()
    _draw_bubbles(target, ["AAAA", "", "AAAA"])
    _draw_small_lettering(target, "nn..")
    ref = art.copy()
    _draw_steam(ref)
    _draw_bubbles(ref, ["HELLO", "", "HELLO"])
    _draw_small_lettering(ref, _SMALL_LETTERING)
    bubbles = [
        (int((fx - fw) * w) - PAD, int((fy - fh) * h) - PAD,
         int((fx + fw) * w) + PAD, int((fy + fh) * h) + PAD)
        for fx, fy, fw, fh in _BUBBLE_LAYOUT
    ]
    return gray(ref), gray(target), bubbles


def gray(img: np.ndarray) -> np.ndarray:
    """BGR -> single-channel grayscale (what `align` takes)."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


@pytest.fixture
def pair():
    """`make_pair()` — (target, reference, bubbles), grayscale art."""
    return make_pair()
