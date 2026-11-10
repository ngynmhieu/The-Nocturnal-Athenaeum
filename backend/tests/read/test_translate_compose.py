import cv2
import numpy as np
import pytest

from backend.app.modules.read.translate import TranslateRefusal, translate_by_reference
from backend.app.modules.read.translate.regions import GlyphHeuristic, match_tone, text_mask

from .conftest import edited_patch_box, furigana_boxes, gray, make_pair, make_steam_grays, steam_box


def test_bubbles_get_reference_text(pair):
    target, reference, bubbles = pair
    out = translate_by_reference(target, reference)
    for (x0, y0, x1, y1) in bubbles:  # bubble boxes in target coordinates
        assert np.abs(out[y0:y1, x0:x1].astype(int) - target[y0:y1, x0:x1]).mean() > 5


def test_art_outside_text_untouched(pair):
    target, reference, bubbles = pair
    out = translate_by_reference(target, reference)
    outside = np.ones(target.shape[:2], bool)
    for (x0, y0, x1, y1) in bubbles:
        outside[y0:y1, x0:x1] = False
    assert np.array_equal(out[outside], target[outside])  # includes the edited-art patch area


def test_edited_art_patch_is_not_copied(pair):
    target, reference, _ = pair
    out = translate_by_reference(target, reference)
    x0, y0, x1, y1 = edited_patch_box()
    assert np.array_equal(out[y0:y1, x0:x1], target[y0:y1, x0:x1])


def test_identical_text_is_refused(pair):
    target, _, _ = pair
    ref = cv2.resize(target, None, fx=1.84, fy=1.84)
    with pytest.raises(TranslateRefusal) as e:
        translate_by_reference(target, ref)
    assert e.value.message == "Nothing to translate: these pages have the same text."


def test_color_page_keeps_color_and_art():
    target, reference, bubbles = make_pair(color=True)
    out = translate_by_reference(target, reference)
    assert out.shape == target.shape and out.ndim == 3
    assert not np.array_equal(out[..., 0], out[..., 2])  # still colour, not collapsed to grey


def test_match_tone_is_identity_without_samples():
    g = np.full((50, 50), 200, np.uint8)
    lut = match_tone(g, g, np.zeros((50, 50), bool))
    assert np.array_equal(lut, np.arange(256, dtype=np.uint8))


def test_text_mask_empty_when_pages_match():
    g = gray(make_pair()[0])
    mask = text_mask(g, g, np.ones_like(g, bool), GlyphHeuristic())
    assert mask.sum() == 0


def test_furigana_marks_are_replaced():
    target, reference, _ = make_pair()
    out = translate_by_reference(target, reference)
    for (x0, y0, x1, y1) in furigana_boxes():
        assert (target[y0:y1, x0:x1] < 200).any()  # the fixture really has a mark here
        assert out[y0:y1, x0:x1].min() >= 200  # and no ghost of it survives



def test_steam_is_not_taken_for_lettering():
    ref, tgt, bubbles = make_steam_grays()
    mask = text_mask(ref, tgt, np.ones_like(tgt, bool))
    outside = np.ones(tgt.shape, bool)
    for (x0, y0, x1, y1) in bubbles:
        outside[y0:y1, x0:x1] = False
    x0, y0, x1, y1 = steam_box()
    assert outside[y0:y1, x0:x1].any()  # the steam really reaches past the bubble
    assert mask[outside].sum() == 0


def test_every_bubble_is_found_despite_steam_and_small_lettering():
    ref, tgt, bubbles = make_steam_grays()
    mask = text_mask(ref, tgt, np.ones_like(tgt, bool))
    for i, (x0, y0, x1, y1) in enumerate(bubbles):
        assert mask[y0:y1, x0:x1].sum() > 0, f"bubble {i + 1} was not found"
